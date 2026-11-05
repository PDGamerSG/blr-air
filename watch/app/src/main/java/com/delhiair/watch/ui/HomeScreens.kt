package com.delhiair.watch.ui

import android.Manifest
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.speech.RecognizerIntent
import android.speech.tts.TextToSpeech
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import android.app.RemoteInput
import androidx.wear.compose.foundation.lazy.ScalingLazyColumn
import androidx.wear.compose.foundation.lazy.ScalingLazyListScope
import androidx.wear.compose.foundation.lazy.rememberScalingLazyListState
import androidx.wear.compose.material3.Button
import androidx.wear.compose.material3.ButtonDefaults
import androidx.wear.compose.material3.Card
import androidx.wear.compose.material3.CircularProgressIndicator
import androidx.wear.compose.material3.FilledTonalButton
import androidx.wear.compose.material3.ListHeader
import androidx.wear.compose.material3.MaterialTheme
import androidx.wear.compose.material3.ScreenScaffold
import androidx.wear.compose.material3.Text
import androidx.wear.input.RemoteInputIntentHelper
import androidx.wear.input.WearableRemoteInputExtender
import com.delhiair.watch.core.LIMITATION
import com.delhiair.watch.core.Recommendation
import com.delhiair.watch.core.SOURCE
import com.delhiair.watch.core.aqiCategory
import com.delhiair.watch.core.assess
import com.delhiair.watch.core.dayLabel
import com.delhiair.watch.core.fixed
import com.delhiair.watch.core.spokenSummary
import com.delhiair.watch.core.windowLabel
import com.delhiair.watch.core.clock
import com.delhiair.watch.data.Station
import com.delhiair.watch.data.headlineAqi
import com.delhiair.watch.data.localStation
import com.delhiair.watch.data.nowSeconds

@Composable
fun Scroller(content: ScalingLazyListScope.() -> Unit) {
    val listState = rememberScalingLazyListState(initialCenterItemIndex = 1)
    ScreenScaffold(scrollState = listState) { padding ->
        ScalingLazyColumn(
            state = listState,
            contentPadding = padding,
            modifier = Modifier.fillMaxSize(),
            content = content,
        )
    }
}

@Composable
fun Centered(text: String, modifier: Modifier = Modifier, color: androidx.compose.ui.graphics.Color = Paper, size: Int = 13) {
    Text(
        text = text,
        color = color,
        fontSize = size.sp,
        textAlign = TextAlign.Center,
        modifier = modifier.fillMaxWidth().padding(horizontal = 8.dp),
    )
}

private fun age(seconds: Long): String = when {
    seconds < 90 -> "just now"
    seconds < 3600 -> "${seconds / 60} min ago"
    else -> "${seconds / 3600} h ago"
}

@Composable
private fun StationLine(station: Station) {
    val now = nowSeconds()
    val stale = if (station.isStale(now)) " (old)" else ""
    val name = station.name.substringBefore(",")
    if (station.isLocal) {
        Centered(
            "Station ${station.aqi} · $name · ${age(now - station.time)}$stale",
            color = aqiColor(station.aqi.toDouble()),
            size = 12,
        )
    } else {
        Centered(
            "Nearest station ${station.aqi} · $name, ${fixed(station.distanceKm, 0)} km away",
            color = Muted,
            size = 12,
        )
    }
}

@Composable
fun HomeScreen(
    state: AirUiState,
    onRefresh: () -> Unit,
    onOpen: (String) -> Unit,
    onAsk: (String) -> Unit,
    onNotice: (String) -> Unit,
    onDismissMessage: () -> Unit,
) {
    val speakLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()?.let(onAsk)
        }
    }
    val askLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == Activity.RESULT_OK && result.data != null) {
            RemoteInput.getResultsFromIntent(result.data!!)?.getCharSequence("request")?.let { onAsk(it.toString()) }
        }
    }
    Scroller {
        val snapshot = state.snapshot
        val current = snapshot?.forecast?.current
        item {
            Text(
                text = snapshot?.location?.name?.substringBefore(",") ?: state.request.place,
                color = Sky,
                fontSize = 13.sp,
                fontWeight = FontWeight.Medium,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 24.dp),
            )
        }
        val station = snapshot?.station
        val local = snapshot?.localStation
        val headline = snapshot?.headlineAqi
        if (headline != null) {
            item {
                val category = aqiCategory(headline)
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.fillMaxWidth().semantics {
                        contentDescription = "US AQI ${fixed(headline, 0)}, $category"
                    },
                ) {
                    Text(
                        fixed(headline, 0),
                        color = aqiColor(headline),
                        fontSize = 46.sp,
                        fontWeight = FontWeight.Bold,
                    )
                    Centered(category, color = aqiColor(headline))
                }
            }
            item {
                val pm = current?.let { "PM2.5 ${fixed(it.pm25, 0)}" }.orEmpty()
                val text = if (local != null) {
                    "Model ${current?.let { fixed(it.usAqi, 0) } ?: "--"} · $pm"
                } else {
                    "US AQI, modelled · $pm"
                }
                Centered(text, color = Muted, size = 12)
            }
        } else if (state.loading) {
            item { CircularProgressIndicator(modifier = Modifier.padding(16.dp)) }
        }
        if (station != null) {
            item { StationLine(station) }
            if (local != null && current != null && local.aqi - current.usAqi >= 50) {
                item {
                    Centered(
                        "Measured air is worse than the forecast model here.",
                        color = aqiColor(local.aqi.toDouble()),
                        size = 12,
                    )
                }
            }
        }
        if (state.asking) {
            item { Centered("Asking the agent…", color = Sky) }
            item { CircularProgressIndicator(modifier = Modifier.padding(8.dp)) }
        }
        state.message?.let { message ->
            item {
                Card(onClick = onDismissMessage, modifier = Modifier.fillMaxWidth()) {
                    Text(message, fontSize = 13.sp, color = Sun)
                }
            }
        }
        state.error?.let { error ->
            item { Centered(error, color = Sun) }
            item { Button(onClick = onRefresh, label = { Text("Try again") }, modifier = Modifier.fillMaxWidth()) }
        }
        val recommendation = state.recommendation
        if (recommendation != null) {
            item { BestWindowCard(recommendation) { onOpen(Routes.WINDOW) } }
        }
        state.noWindow?.let { note ->
            item { ListHeader { Text("No window fits") } }
            item { Centered(note, color = Sun, size = 12) }
        }
        if (snapshot?.offline == true) {
            item {
                Centered("Offline · updated ${age(nowSeconds() - snapshot.forecast.fetchedAt)}", color = Sun, size = 12)
            }
        }
        item {
            // Samsung's keyboard has no mic key, so voice goes straight to the recogniser.
            Button(
                enabled = !state.asking,
                onClick = {
                    val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                        .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                        .putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-IN")
                        .putExtra(RecognizerIntent.EXTRA_PROMPT, "Ask Delhi Air")
                    try {
                        speakLauncher.launch(intent)
                    } catch (_: ActivityNotFoundException) {
                        onNotice("Voice isn't available on this watch. Type your request instead.")
                    }
                },
                label = { Text("Speak to the agent") },
                modifier = Modifier.fillMaxWidth(),
            )
        }
        item {
            FilledTonalButton(
                enabled = !state.asking,
                onClick = {
                    val intent: Intent = RemoteInputIntentHelper.createActionRemoteInputIntent()
                    RemoteInputIntentHelper.putRemoteInputsExtra(
                        intent,
                        listOf(
                            WearableRemoteInputExtender(
                                RemoteInput.Builder("request").setLabel("Ask Delhi Air"),
                            ).setEmojisAllowed(false).get().build(),
                        ),
                    )
                    askLauncher.launch(intent)
                },
                label = { Text("Type to the agent") },
                modifier = Modifier.fillMaxWidth(),
            )
        }
        item {
            FilledTonalButton(
                onClick = { onOpen(Routes.PLACES) },
                label = { Text("Place") },
                secondaryLabel = { Text(snapshot?.location?.name ?: state.request.place) },
                modifier = Modifier.fillMaxWidth(),
            )
        }
        item {
            FilledTonalButton(
                onClick = { onOpen(Routes.PLAN) },
                label = { Text("Plan") },
                secondaryLabel = {
                    Text("${state.request.activity.label} · ${state.request.hours} h · ${state.request.day.label}")
                },
                modifier = Modifier.fillMaxWidth(),
            )
        }
        item {
            FilledTonalButton(
                onClick = { onOpen(Routes.COMPARE_PICK) },
                label = { Text("Compare places") },
                modifier = Modifier.fillMaxWidth(),
            )
        }
        item {
            FilledTonalButton(
                onClick = onRefresh,
                enabled = !state.loading,
                label = { Text(if (state.loading) "Updating…" else "Refresh") },
                secondaryLabel = snapshot?.let { { Text("Updated ${age(nowSeconds() - it.forecast.fetchedAt)}") } },
                modifier = Modifier.fillMaxWidth(),
            )
        }
        item {
            FilledTonalButton(
                onClick = { onOpen(Routes.ABOUT) },
                label = { Text("About this data") },
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

@Composable
private fun BestWindowCard(recommendation: Recommendation, onClick: () -> Unit) {
    val window = recommendation.window
    val timezone = recommendation.forecast.timezone
    val adverse = window.maxAqi > 100
    Card(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Text(
            if (adverse) "Least-bad ${recommendation.request.activity.label.lowercase()}" else "Best ${recommendation.request.activity.label.lowercase()}",
            fontSize = 12.sp,
            color = Muted,
        )
        Text(
            "${clock(window.start, timezone)}–${clock(window.end, timezone)}",
            fontSize = 22.sp,
            fontWeight = FontWeight.Bold,
            color = Paper,
        )
        Text(dayLabel(window.start, timezone), fontSize = 12.sp, color = Muted)
        Text(
            "AQI ${fixed(window.usAqi, 0)} · PM2.5 ${fixed(window.pm25, 0)}",
            fontSize = 13.sp,
            color = aqiColor(window.maxAqi),
        )
        if (adverse) Text("Consider staying indoors", fontSize = 12.sp, color = Sun)
    }
}

@Composable
fun WindowScreen(
    state: AirUiState,
    onRemind: (Recommendation) -> Unit,
    onNotice: (String) -> Unit,
    onDismissMessage: () -> Unit,
) {
    val recommendation = state.recommendation
    if (recommendation == null) {
        Scroller { item { Centered("No window selected.") } }
        return
    }
    var selected by remember { mutableIntStateOf(0) }
    val windows = listOf(recommendation.window) + recommendation.backups
    val window = windows[selected.coerceAtMost(windows.lastIndex)]
    val shown = recommendation.copy(window = window)
    val timezone = recommendation.forecast.timezone
    val result = assess(window, recommendation.request)
    val context = LocalContext.current
    var speech by remember { mutableStateOf<TextToSpeech?>(null) }
    var speechFailed by remember { mutableStateOf(false) }
    val notifications = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) {
            onRemind(shown)
        } else {
            onNotice("Notifications are off, so no reminder was set.")
        }
    }
    DisposableEffect(Unit) { onDispose { speech?.shutdown() } }
    Scroller {
        val found = recommendation.search
        item { ListHeader { Text(if (selected != 0) "Backup $selected" else if (found != null) "Best place" else "Best available") } }
        if (found != null) item { Centered(found.place, color = Sun, size = 17) }
        if (state.fromAgent) item { Centered("From the Delhi Air agent", color = Sky, size = 12) }
        item { Centered(windowLabel(window, timezone), size = 15) }
        if (found != null) {
            item { Centered(found.why, size = 12) }
            item {
                Centered(
                    "Compared ${found.checked} of ${found.searched} places near ${found.area}.",
                    color = Muted,
                    size = 12,
                )
            }
        }
        item { Centered(result.verdict, color = if (window.maxAqi > 100) Sun else Paper, size = 12) }
        item { Fact("Air", "AQI ${fixed(window.usAqi, 0)} avg · worst ${fixed(window.maxAqi, 0)}") }
        item { Fact("Category", result.category) }
        item { Fact("PM2.5", "${fixed(window.pm25, 1)} µg/m³") }
        item { Fact("Rain", "${fixed(window.rain, 0)}% peak hourly") }
        item { Fact("Heat", "${fixed(window.temperature, 1)}°C" + (window.apparent?.let { ", feels ${fixed(it, 1)}°C" } ?: "")) }
        window.uv?.let { item { Fact("UV", fixed(it, 1)) } }
        window.wind?.let { item { Fact("Wind", "${fixed(it, 1)} km/h") } }
        item {
            Fact(
                "Daylight",
                when (window.daylight) {
                    true -> "Fully in daylight"
                    false -> "Not fully in daylight"
                    null -> "Unavailable"
                },
            )
        }
        state.message?.let { message ->
            item {
                Card(onClick = onDismissMessage, modifier = Modifier.fillMaxWidth()) {
                    Text(message, fontSize = 13.sp, color = Sun)
                }
            }
        }
        item {
            Button(
                onClick = {
                    val needed = Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
                    val allowed = ContextCompat.checkSelfPermission(
                        context,
                        Manifest.permission.POST_NOTIFICATIONS,
                    ) == PackageManager.PERMISSION_GRANTED
                    if (needed && !allowed) {
                        notifications.launch(Manifest.permission.POST_NOTIFICATIONS)
                    } else {
                        onRemind(shown)
                    }
                },
                label = { Text("Remind me") },
                secondaryLabel = { Text("1 h before, to recheck") },
                modifier = Modifier.fillMaxWidth(),
            )
        }
        item {
            FilledTonalButton(
                onClick = {
                    val text = spokenSummary(shown)
                    val current = speech
                    if (current != null) {
                        current.speak(text, TextToSpeech.QUEUE_FLUSH, null, "plan")
                    } else {
                        lateinit var engine: TextToSpeech
                        engine = TextToSpeech(context) { status ->
                            if (status == TextToSpeech.SUCCESS) {
                                engine.language = java.util.Locale("en", "IN")
                                engine.speak(text, TextToSpeech.QUEUE_FLUSH, null, "plan")
                            } else {
                                speechFailed = true
                                speech = null
                                engine.shutdown()
                            }
                        }
                        speech = engine
                    }
                },
                label = { Text("Read aloud") },
                secondaryLabel = if (speechFailed) ({ Text("No speech engine on this watch") }) else null,
                modifier = Modifier.fillMaxWidth(),
            )
        }
        windows.indices.filter { it != selected }.forEach { index ->
            item {
                FilledTonalButton(
                    onClick = { selected = index },
                    label = { Text(if (index == 0) "Best window" else "Backup $index") },
                    secondaryLabel = {
                        Text("${clock(windows[index].start, timezone)} · AQI ${fixed(windows[index].usAqi, 0)}")
                    },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }
        if (found != null && found.others.isNotEmpty()) {
            item { ListHeader { Text("Other places") } }
            found.others.forEach { other ->
                item {
                    Card(onClick = {}, modifier = Modifier.fillMaxWidth()) {
                        Text(other.place, fontSize = 14.sp, color = Paper)
                        Text("${fixed(other.distanceKm, 1)} km · ${other.time}", fontSize = 12.sp, color = Muted)
                        Text(
                            "AQI ${other.aqi}" + (other.measured?.let { " · monitor $it" } ?: ""),
                            fontSize = 13.sp,
                            color = aqiColor((other.measured ?: other.aqi).toDouble()),
                        )
                    }
                }
            }
        }
        if (result.checklist.size > 2) item { ListHeader { Text("Before you go") } }
        items(result.checklist.drop(2).size) { index ->
            Centered(result.checklist[index + 2], size = 12)
        }
        item { ListHeader { Text("Worth knowing") } }
        items(result.warnings.size) { index -> Centered(result.warnings[index], color = Muted, size = 12) }
        // Above AQI 50 the advice is already part of the warnings.
        if (window.maxAqi <= 50) item { Centered(result.advice, color = Muted, size = 12) }
    }
}

@Composable
private fun Fact(label: String, value: String) {
    Column(
        verticalArrangement = Arrangement.spacedBy(0.dp),
        modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp),
    ) {
        Text(label, fontSize = 11.sp, color = Muted)
        Text(value, fontSize = 14.sp, color = Paper)
    }
}

@Composable
fun AnswerScreen(text: String) {
    Scroller {
        item { ListHeader { Text("Delhi Air agent") } }
        text.split("\n\n").filter { it.isNotBlank() }.forEach { part ->
            item { Centered(part.trim()) }
        }
    }
}

@Composable
fun AboutScreen(state: AirUiState, stationsConfigured: Boolean, agentConfigured: Boolean) {
    Scroller {
        item { ListHeader { Text("About this data") } }
        item {
            Centered(
                if (agentConfigured) {
                    "Ask goes to the Delhi Air agent. If it can't be reached, the watch plans by itself."
                } else {
                    "No agent address is set, so the watch plans by itself."
                },
                size = 12,
            )
        }
        item { Centered("Forecast: $SOURCE.", size = 12) }
        item { Centered(LIMITATION, color = Muted, size = 12) }
        item {
            Centered(
                "The model covers about 45 km per cell, so nearby localities often share a forecast. " +
                    "It cannot see local hotspots.",
                color = Muted,
                size = 12,
            )
        }
        item {
            val station = state.snapshot?.station
            val text = when {
                !stationsConfigured -> "Station readings are off: no WAQI token is set."
                station != null -> "Nearest station: ${station.name}, ${fixed(station.distanceKm, 1)} km away" +
                    (station.dominant?.let { ", mainly $it" } ?: "") + ". " +
                    (if (station.isLocal) "" else "Too far to represent this place, so the model is shown. ") +
                    "Data: World Air Quality Index project and ${station.attribution}."
                else -> "No station with a current reading within 15 km of this place."
            }
            Centered(text, size = 12)
        }
        item { Centered("Only 05:00–21:00 windows count. The best window can still be unhealthy. Not medical advice.", color = Muted, size = 12) }
        item { Centered("Times use ${state.snapshot?.forecast?.timezone ?: "the place's timezone"}.", color = Muted, size = 12) }
    }
}
