package com.delhiair.watch.ui

import android.app.Activity
import android.app.RemoteInput
import android.content.ActivityNotFoundException
import android.content.Intent
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.wear.compose.material3.Button
import androidx.wear.compose.material3.ButtonDefaults
import androidx.wear.compose.material3.Card
import androidx.wear.compose.material3.CircularProgressIndicator
import androidx.wear.compose.material3.Icon
import androidx.wear.compose.material3.Text
import androidx.wear.input.RemoteInputIntentHelper
import androidx.wear.input.WearableRemoteInputExtender
import com.delhiair.watch.R
import com.delhiair.watch.core.Activity as Outing
import com.delhiair.watch.core.LIMITATION
import com.delhiair.watch.core.Recommendation
import com.delhiair.watch.core.SOURCE
import com.delhiair.watch.core.aqiCategory
import com.delhiair.watch.core.clock
import com.delhiair.watch.core.dayLabel
import com.delhiair.watch.core.fixed
import com.delhiair.watch.data.Snapshot
import com.delhiair.watch.data.headlineAqi
import com.delhiair.watch.data.localStation
import com.delhiair.watch.data.nowSeconds
import kotlinx.coroutines.delay

private fun age(seconds: Long): String = when {
    seconds < 90 -> "just now"
    seconds < 3600 -> "${seconds / 60} min ago"
    else -> "${seconds / 3600} h ago"
}

/** The agent may be reachable when the forecast isn't, so its reading fills the gap. */
private fun heroAqi(state: AirUiState): Double? =
    state.snapshot?.headlineAqi ?: state.forYou?.suggestion?.nowAqi?.toDouble()

@Composable
private fun Hero(state: AirUiState, snapshot: Snapshot?, onAsk: () -> Unit, modifier: Modifier = Modifier) {
    val headline = heroAqi(state)
    val height = LocalConfiguration.current.screenHeightDp.dp
    val glow = headline?.let(::aqiColor) ?: Sky
    Box(
        contentAlignment = Alignment.Center,
        modifier = modifier
            .fillMaxWidth()
            .height(height - 22.dp)
            .background(Brush.radialGradient(listOf(glow.copy(alpha = 0.20f), Color.Transparent))),
    ) {
        if (headline == null) {
            if (state.error == null) {
                CircularProgressIndicator(modifier = Modifier.size(56.dp))
            } else {
                Centered("No air data right now. Scroll down to retry.", color = Sun, size = 14, modifier = Modifier.padding(horizontal = 30.dp))
            }
            AskButton(state.asking, onAsk, Modifier.align(Alignment.BottomCenter))
            return@Box
        }
        val category = aqiCategory(headline)
        val local = snapshot?.localStation
        val current = snapshot?.forecast?.current
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.align(Alignment.TopCenter).padding(start = 20.dp, end = 20.dp, top = 26.dp).semantics {
                contentDescription = "US AQI ${fixed(headline, 0)}, $category"
            },
        ) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(3.dp)) {
                SmallIcon(R.drawable.ic_pin, Sky, 14.dp)
                Text(
                    snapshot?.location?.name?.substringBefore(",") ?: "Near you",
                    color = Sky,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Text(fixed(headline, 0), color = glow, fontSize = 46.sp, lineHeight = 50.sp, fontWeight = FontWeight.Black, maxLines = 1)
            Text(
                category,
                color = glow,
                fontSize = 15.sp,
                lineHeight = 17.sp,
                fontWeight = FontWeight.SemiBold,
                textAlign = TextAlign.Center,
                maxLines = 2,
            )
            val source = when {
                snapshot == null -> "From the agent"
                snapshot.offline -> "Offline · ${age(nowSeconds() - snapshot.forecast.fetchedAt)}"
                local != null && current != null -> "Monitor · model ${fixed(current.usAqi, 0)}"
                local != null -> "Live monitor"
                else -> "Forecast model"
            }
            Text(
                source,
                color = if (snapshot?.offline == true) Sun else Muted,
                fontSize = 12.sp,
                maxLines = 1,
                modifier = Modifier.padding(top = 1.dp),
            )
        }
        AskButton(state.asking, onAsk, Modifier.align(Alignment.BottomCenter))
    }
}

@Composable
private fun AskButton(asking: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier) {
    Button(
        onClick = onClick,
        enabled = !asking,
        modifier = modifier.padding(bottom = 6.dp).height(46.dp),
        icon = { Icon(painterResource(R.drawable.ic_mic), contentDescription = null, modifier = Modifier.size(20.dp)) },
        label = { Text("Ask", fontWeight = FontWeight.Bold) },
    )
}

/** The agent speaking first: what it thinks you should do, without being asked. */
@Composable
private fun ForYou(plan: Recommendation, onOpen: () -> Unit, onNotForMe: () -> Unit) {
    val advice = plan.suggestion ?: return
    val tone = when (advice.kind) {
        "go" -> aqiColor(40.0)
        "care" -> aqiColor(130.0)
        "short" -> aqiColor(180.0)
        else -> aqiColor(260.0)
    }
    Card(onClick = onOpen, modifier = Modifier.fillMaxWidth()) {
        Column {
            Text("FOR YOU", color = Sky, fontSize = 11.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.sp)
            Text(advice.headline, color = tone, fontSize = 19.sp, fontWeight = FontWeight.Bold, lineHeight = 22.sp)
            Text(advice.detail, color = Paper, fontSize = 13.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
            advice.reasons.firstOrNull()?.let {
                Text(
                    it,
                    color = Muted,
                    fontSize = 12.sp,
                    maxLines = 3,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(top = 3.dp),
                )
            }
        }
    }
    Text(
        "Not for me",
        color = Muted,
        fontSize = 12.sp,
        modifier = Modifier.clickable(onClick = onNotForMe).padding(horizontal = 16.dp, vertical = 6.dp),
    )
}

@Composable
private fun NextTime(recommendation: Recommendation, onClick: () -> Unit) {
    val window = recommendation.window
    val timezone = recommendation.forecast.timezone
    val verdict = verdictStyle(window, recommendation.request)
    Card(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    if (window.maxAqi > 100) "Least-bad time" else "Best time",
                    color = Muted,
                    fontSize = 12.sp,
                )
                Text(
                    "${clock(window.start, timezone)}–${clock(window.end, timezone)}",
                    color = Paper,
                    fontSize = 21.sp,
                    fontWeight = FontWeight.Bold,
                    maxLines = 1,
                )
                Text(
                    "${dayLabel(window.start, timezone)} · AQI ${fixed(window.usAqi, 0)}",
                    color = verdict.color,
                    fontSize = 12.sp,
                    maxLines = 1,
                )
            }
        }
    }
}

@Composable
fun HomeScreen(
    state: AirUiState,
    onRefresh: () -> Unit,
    onOpen: (String) -> Unit,
    onAsk: (String) -> Unit,
    onQuickAsk: (Outing) -> Unit,
    onForYou: () -> Unit,
    onNotForMe: () -> Unit,
    onNotice: (String) -> Unit,
    onDismissMessage: () -> Unit,
) {
    val speakLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()?.let(onAsk)
        }
    }
    val typeLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == Activity.RESULT_OK && result.data != null) {
            RemoteInput.getResultsFromIntent(result.data!!)?.getCharSequence("request")?.let { onAsk(it.toString()) }
        }
    }
    val speak = {
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-IN")
            .putExtra(RecognizerIntent.EXTRA_PROMPT, "Where do you want to go?")
        // Samsung's keyboard has no mic key, so voice goes straight to the recogniser.
        try {
            speakLauncher.launch(intent)
        } catch (_: ActivityNotFoundException) {
            onNotice("Voice isn't available on this watch. Type your request instead.")
        }
    }
    val listState = rememberLazyListState()
    // The ring belongs to the hero, so it fades as the hero scrolls away.
    val ringAlpha by remember {
        derivedStateOf {
            if (listState.firstVisibleItemIndex > 0) 0f else 1f - (listState.firstVisibleItemScrollOffset / 160f).coerceIn(0f, 1f)
        }
    }
    Box(Modifier.fillMaxSize()) {
        Scroller(listState = listState) {
            val snapshot = state.snapshot
            item { Hero(state, snapshot, speak) }
            state.forYou?.let { plan -> item { Column(horizontalAlignment = Alignment.CenterHorizontally) { ForYou(plan, onForYou, onNotForMe) } } }
            state.message?.let { message ->
                item {
                    Card(onClick = onDismissMessage, modifier = Modifier.fillMaxWidth()) {
                        Text(message, fontSize = 13.sp, color = Sun)
                    }
                }
            }
            state.error?.let { error ->
                item { Centered(error, color = Sun) }
                item {
                    Button(onClick = onRefresh, label = { Text("Try again") }, modifier = Modifier.fillMaxWidth())
                }
            }
            if (state.forYou == null) {
                state.recommendation?.let { plan ->
                    item { NextTime(plan) { onOpen(Routes.WINDOW) } }
                }
            }
            state.noWindow?.let { note ->
                item { Panel { Centered(note, color = Sun, size = 12) } }
            }
            item { SectionTitle("Find me a place") }
            item {
                Row(horizontalArrangement = Arrangement.SpaceEvenly, modifier = Modifier.fillMaxWidth()) {
                    RoundAction(R.drawable.ic_walk, "Walk", { onQuickAsk(Outing.WALK) }, enabled = !state.asking)
                    RoundAction(R.drawable.ic_run, "Run", { onQuickAsk(Outing.RUN) }, enabled = !state.asking)
                }
            }
            item {
                Row(horizontalArrangement = Arrangement.SpaceEvenly, modifier = Modifier.fillMaxWidth()) {
                    RoundAction(R.drawable.ic_bike, "Ride", { onQuickAsk(Outing.CYCLE) }, enabled = !state.asking)
                    RoundAction(R.drawable.ic_kids, "Kids", { onQuickAsk(Outing.KIDS) }, enabled = !state.asking)
                }
            }
            item { SectionTitle("More") }
            item {
                MenuRow(R.drawable.ic_keyboard, "Type a request", enabled = !state.asking) {
                    val intent: Intent = RemoteInputIntentHelper.createActionRemoteInputIntent()
                    RemoteInputIntentHelper.putRemoteInputsExtra(
                        intent,
                        listOf(
                            WearableRemoteInputExtender(
                                RemoteInput.Builder("request").setLabel("Ask Delhi Air"),
                            ).setEmojisAllowed(false).get().build(),
                        ),
                    )
                    typeLauncher.launch(intent)
                }
            }
            item {
                MenuRow(R.drawable.ic_pin, "Place", snapshot?.location?.name?.substringBefore(",") ?: state.request.place) {
                    onOpen(Routes.PLACES)
                }
            }
            item {
                MenuRow(
                    R.drawable.ic_tune,
                    "Plan",
                    "${state.request.activity.label} · ${state.request.hours} h · ${state.request.day.label}",
                ) { onOpen(Routes.PLAN) }
            }
            item { MenuRow(R.drawable.ic_compare, "Compare places") { onOpen(Routes.COMPARE_PICK) } }
            item {
                MenuRow(
                    R.drawable.ic_refresh,
                    if (state.loading) "Updating…" else "Refresh",
                    snapshot?.let { "Updated ${age(nowSeconds() - it.forecast.fetchedAt)}" },
                    enabled = !state.loading,
                    onClick = onRefresh,
                )
            }
            item { MenuRow(R.drawable.ic_info, "About this data") { onOpen(Routes.ABOUT) } }
            item { Box(Modifier.height(28.dp)) }
        }
        heroAqi(state)?.let { aqi -> AqiRing(aqi, Modifier.fillMaxSize().alpha(ringAlpha)) }
    }
}

private val THINKING = listOf(
    "Reading your request",
    "Searching nearby places",
    "Checking forecasts",
    "Reading live monitors",
    "Choosing the best option",
)

/** The agent can take several seconds, so the wait shows what it is doing. */
@Composable
fun Thinking() {
    var step by remember { mutableIntStateOf(0) }
    LaunchedEffect(Unit) {
        while (true) {
            delay(1500)
            step = (step + 1) % THINKING.size
        }
    }
    Box(
        contentAlignment = Alignment.Center,
        modifier = Modifier.fillMaxSize().background(Color.Black),
    ) {
        CircularProgressIndicator(modifier = Modifier.fillMaxSize().padding(6.dp))
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(horizontal = 34.dp)) {
            Image(
                painterResource(R.drawable.ic_launcher_foreground),
                contentDescription = null,
                modifier = Modifier.size(84.dp),
            )
            Text("Asking the agent", color = Paper, fontSize = 15.sp, fontWeight = FontWeight.Bold)
            Text(
                THINKING[step],
                color = Sky,
                fontSize = 13.sp,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 2.dp),
            )
        }
    }
}

private val AQI_LINE = Regex("""US AQI (\d+)(?:–\d+)? ?\(?([A-Za-z ]+)?\)?""")

/** Chat replies are built for reading on a phone; this gives them structure on a small screen. */
@Composable
fun AnswerScreen(text: String, heard: String? = null) {
    val blocks = text.split("\n\n").map { it.trim() }.filter { it.isNotEmpty() }
    val aqi = AQI_LINE.find(text)?.groupValues?.get(1)?.toDoubleOrNull()
    Scroller {
        item { Box(Modifier.height(4.dp)) }
        if (aqi != null) {
            item {
                Box(contentAlignment = Alignment.Center, modifier = Modifier.size(132.dp)) {
                    AqiRing(aqi, Modifier.fillMaxSize(), thickness = 7.dp)
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(fixed(aqi, 0), color = aqiColor(aqi), fontSize = 38.sp, fontWeight = FontWeight.Black)
                        Text("US AQI", color = Muted, fontSize = 11.sp)
                    }
                }
            }
            item { Pill(aqiCategory(aqi), aqiColor(aqi)) }
        }
        blocks.forEach { block ->
            val lines = block.lines().map { it.trim() }
            when {
                lines.all { it.startsWith("• ") } -> item {
                    Panel {
                        Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
                            lines.forEach { Bullet(it.removePrefix("• ")) }
                        }
                    }
                }
                block.startsWith("Forecast retrieved") || block.startsWith("Source:") ->
                    item { Centered(block, color = Muted, size = 11) }
                block.length <= 48 && !block.endsWith(".") -> item {
                    Text(
                        block,
                        color = Sun,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
                    )
                }
                else -> item { Centered(block, size = 14) }
            }
        }
        heard?.let { words -> item { Centered("You said: $words", color = Muted, size = 11) } }
        item { Box(Modifier.height(24.dp)) }
    }
}

@Composable
fun AboutScreen(state: AirUiState, stationsConfigured: Boolean, agentConfigured: Boolean) {
    Scroller {
        item { SectionTitle("About this data") }
        item {
            Panel {
                Centered(
                    if (agentConfigured) {
                        "Ask goes to the Delhi Air agent. If it can't be reached, the watch plans by itself."
                    } else {
                        "No agent address is set, so the watch plans by itself."
                    },
                )
            }
        }
        item {
            Panel {
                Centered(
                    "The agent learns what you plan, when you ask and how much you move. That history " +
                        "stays on the watch. Only your position, usual hours and top activities reach " +
                        "the agent. It speaks up at most twice a day, never 22:00–07:00.",
                )
            }
        }
        item {
            val station = state.snapshot?.station
            val text = when {
                !stationsConfigured -> "Station readings are off: no WAQI token is set."
                station != null -> "Nearest monitor: ${station.name}, ${fixed(station.distanceKm, 1)} km away" +
                    (station.dominant?.let { ", mainly $it" } ?: "") + ". " +
                    (if (station.isLocal) "" else "Too far to represent this place, so the model is shown. ") +
                    "Data: World Air Quality Index project and ${station.attribution}."
                else -> "No monitor with a current reading within 15 km of this place."
            }
            Panel { Centered(text) }
        }
        item {
            Panel {
                Centered(
                    "Forecast: $SOURCE. Each model cell covers about 45 km, so nearby places often share " +
                        "a forecast and it can't see local hotspots.",
                )
            }
        }
        item { Centered("Places from OpenStreetMap contributors.", color = Muted, size = 12) }
        item {
            Centered(
                "Only 05:00–21:00 windows count. The best window can still be unhealthy. $LIMITATION",
                color = Muted,
                size = 12,
            )
        }
        item { Box(Modifier.height(24.dp)) }
    }
}
