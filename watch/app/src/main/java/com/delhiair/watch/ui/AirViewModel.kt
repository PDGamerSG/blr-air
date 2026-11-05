package com.delhiair.watch.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.delhiair.watch.BuildConfig
import com.delhiair.watch.core.AirException
import com.delhiair.watch.core.Comparison
import com.delhiair.watch.core.ComparisonItem
import com.delhiair.watch.core.PlanRequest
import com.delhiair.watch.core.Recommendation
import com.delhiair.watch.core.parseLocal
import com.delhiair.watch.core.recommend
import com.delhiair.watch.data.AgentClient
import com.delhiair.watch.data.AgentReply
import com.delhiair.watch.data.AgentUnavailable
import com.delhiair.watch.data.AirRepository
import com.delhiair.watch.data.MAX_OFFLINE_SECONDS
import com.delhiair.watch.data.Snapshot
import com.delhiair.watch.data.localStation
import com.delhiair.watch.data.nowSeconds
import com.delhiair.watch.work.Reminders
import com.delhiair.watch.work.refreshSurfaces
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private const val STALE_AFTER_SECONDS = 300L

data class AirUiState(
    val loading: Boolean = true,
    val request: PlanRequest = PlanRequest(),
    val snapshot: Snapshot? = null,
    val recommendation: Recommendation? = null,
    /** Set when the forecast loaded but no window fits the request. */
    val noWindow: String? = null,
    /** Set when the forecast itself could not be loaded. */
    val error: String? = null,
    val comparison: Comparison? = null,
    val comparing: Boolean = false,
    val asking: Boolean = false,
    /** The agent's own words, for questions that aren't plans. */
    val agentAnswer: String? = null,
    /** True when the shown plan came from the agent rather than the watch. */
    val fromAgent: Boolean = false,
    /** The words the agent was given, so a mishearing is visible. */
    val heard: String? = null,
    val message: String? = null,
)

class AirViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = AirRepository(application)
    private val agent = AgentClient(BuildConfig.AGENT_URL)
    private val _state = MutableStateFlow(AirUiState(request = repository.loadRequest()))
    val state: StateFlow<AirUiState> = _state.asStateFlow()

    val stationsConfigured get() = repository.stationsConfigured
    val agentConfigured get() = agent.configured
    private var notice: Job? = null

    // Blocking HTTP can't be cancelled, so a generation number stops late results landing.
    private var loadJob: Job? = null
    private var loadGeneration = 0
    private var compareJob: Job? = null
    private var compareGeneration = 0

    init {
        refresh()
    }

    fun refresh(force: Boolean = false) = load(_state.value.request, force)

    /** Called when the app returns to the screen, which can be hours later on a watch. */
    fun refreshIfStale() {
        val current = _state.value
        if (current.asking || current.loading) return
        val fetched = current.snapshot?.forecast?.fetchedAt
        if (fetched == null || nowSeconds() - fetched >= STALE_AFTER_SECONDS) refresh()
    }

    fun update(request: PlanRequest, then: (() -> Unit)? = null) =
        load(request, force = false, save = true, then = then)

    fun usePlace(place: String) = update(_state.value.request.copy(place = place))

    fun useCoordinates(latitude: Double, longitude: Double) {
        usePlace("%.4f, %.4f".format(java.util.Locale.ROOT, latitude, longitude))
    }

    /** Requests go to the agent; the watch only plans for itself when it can't reach it. */
    fun ask(text: String, open: (String) -> Unit) {
        if (_state.value.asking) return
        _state.update { it.copy(asking = true, heard = text) }
        viewModelScope.launch {
            try {
                val near = _state.value.snapshot?.location
                val reply = withContext(Dispatchers.IO) { agent.ask(text, near) }
                showReply(reply, open)
            } catch (_: AgentUnavailable) {
                askLocally(text, open)
            } catch (exc: AirException) {
                say(exc.message.orEmpty())
            } finally {
                _state.update { it.copy(asking = false) }
            }
        }
    }

    private fun showReply(reply: AgentReply, open: (String) -> Unit) {
        when (reply) {
            is AgentReply.Answer -> {
                _state.update { it.copy(agentAnswer = reply.text) }
                open(Routes.ANSWER)
            }
            is AgentReply.Plan -> {
                val plan = reply.recommendation
                // The agent resolved this place, so the watch must not guess it again.
                repository.remember(plan.request.place, plan.location)
                repository.saveRequest(plan.request)
                load(plan.request, force = false, agentPlan = plan)
                open(Routes.WINDOW)
            }
            is AgentReply.Compared -> {
                showComparison(reply.comparison)
                open(Routes.COMPARE)
            }
        }
    }

    /** Show the agent's ranking at once, then add what nearby monitors say. */
    private fun showComparison(comparison: Comparison) {
        val generation = ++compareGeneration
        compareJob?.cancel()
        _state.update { it.copy(comparing = false, comparison = comparison) }
        compareJob = viewModelScope.launch {
            val items = comparison.items.map { item ->
                val location = item.recommendation?.location ?: return@map item
                val measured = try {
                    repository.snapshot(location, freshSeconds = 1800).localStation?.aqi?.toDouble()
                } catch (_: AirException) {
                    null
                }
                item.copy(measuredAqi = measured)
            }
            if (generation == compareGeneration) {
                _state.update { it.copy(comparison = Comparison(items, comparison.sharedAirModel)) }
            }
        }
    }

    private fun askLocally(text: String, open: (String) -> Unit) {
        val notice = "Agent unreachable, so the watch planned this itself."
        try {
            val parsed = parseLocal(text)
            if (parsed.places.size > 1) {
                compare(parsed.places, parsed)
                open(Routes.COMPARE)
                if (agent.configured) say(notice)
            } else {
                update(parsed) {
                    if (agent.configured) say(notice)
                    if (_state.value.recommendation != null) open(Routes.WINDOW)
                }
            }
        } catch (exc: AirException) {
            say(exc.message.orEmpty())
        }
    }

    fun clearMessage() = _state.update { it.copy(message = null) }

    /** Short notices go away by themselves, so they can't linger on the home screen. */
    fun say(message: String) {
        _state.update { it.copy(message = message) }
        notice?.cancel()
        notice = viewModelScope.launch {
            delay(5000)
            clearMessage()
        }
    }

    fun remind(recommendation: Recommendation) {
        say(Reminders.schedule(getApplication(), recommendation))
    }

    /**
     * [save] keeps a new request only once it has proved usable, so one misheard place can't
     * break the home screen, tile and complication.
     */
    private fun load(
        request: PlanRequest,
        force: Boolean,
        save: Boolean = false,
        agentPlan: Recommendation? = null,
        then: (() -> Unit)? = null,
    ) {
        val previous = _state.value
        val generation = ++loadGeneration
        loadJob?.cancel()
        // Show the saved forecast straight away: a raised wrist can't wait for the network.
        val saved = repository.cached(request)
        val instant = saved?.takeIf { nowSeconds() - it.forecast.fetchedAt <= MAX_OFFLINE_SECONDS }
        val early = agentPlan?.let { it to null } ?: instant?.let { plan(request, it) }
        _state.update {
            it.copy(
                loading = true,
                request = request,
                error = null,
                noWindow = early?.second,
                snapshot = instant,
                recommendation = early?.first,
                fromAgent = agentPlan != null,
            )
        }
        loadJob = viewModelScope.launch {
            try {
                val location = agentPlan?.location ?: repository.resolve(request.place)
                val snapshot = repository.snapshot(location, force)
                if (generation != loadGeneration) return@launch
                val plan = agentPlan?.let { it to null } ?: plan(request, snapshot)
                if (save) repository.saveRequest(request)
                _state.update {
                    it.copy(
                        loading = false,
                        snapshot = snapshot,
                        recommendation = plan.first,
                        noWindow = plan.second,
                        fromAgent = agentPlan != null,
                    )
                }
                refreshSurfaces(getApplication())
                then?.invoke()
            } catch (exc: AirException) {
                if (generation != loadGeneration) return@launch
                when {
                    // The agent's answer stands even if the watch can't fetch its own copy.
                    agentPlan != null -> _state.update {
                        it.copy(loading = false, recommendation = agentPlan, fromAgent = true)
                    }
                    save -> {
                        _state.value = previous.copy(loading = false)
                        say(exc.message.orEmpty())
                    }
                    else -> _state.update {
                        it.copy(loading = false, snapshot = null, recommendation = null, error = exc.message)
                    }
                }
            }
        }
    }

    private fun plan(request: PlanRequest, snapshot: Snapshot): Pair<Recommendation?, String?> = try {
        recommend(request, snapshot.location, snapshot.forecast, nowSeconds()) to null
    } catch (exc: AirException) {
        null to exc.message
    }

    /** A spoken comparison brings its own activity and time; the picker uses the saved plan. */
    fun compare(places: List<String>, request: PlanRequest = _state.value.request) {
        val generation = ++compareGeneration
        compareJob?.cancel()
        _state.update { it.copy(comparing = true, comparison = null) }
        compareJob = viewModelScope.launch {
            // One place at a time: a watch link rarely copes with many requests at once.
            val items = places.map { place ->
                try {
                    val location = repository.resolve(place)
                    // Forecasts change slowly; a recent saved one saves a slow round trip.
                    val snapshot = repository.snapshot(location, freshSeconds = 1800)
                    ComparisonItem(
                        place,
                        recommend(request.copy(place = place), location, snapshot.forecast, nowSeconds()),
                        measuredAqi = snapshot.localStation?.aqi?.toDouble(),
                    )
                } catch (exc: AirException) {
                    ComparisonItem(place, error = exc.message)
                }
            }
            if (generation == compareGeneration) {
                _state.update { it.copy(comparing = false, comparison = Comparison(items)) }
            }
        }
    }
}
