package com.delhiair.watch.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.speech.tts.TextToSpeech
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.wear.compose.material3.Card
import androidx.wear.compose.material3.Text
import com.delhiair.watch.R
import com.delhiair.watch.core.Activity as Outing
import com.delhiair.watch.core.PlanRequest
import com.delhiair.watch.core.Verdict
import com.delhiair.watch.core.Window
import com.delhiair.watch.core.assess
import com.delhiair.watch.core.clock
import com.delhiair.watch.core.dayLabel
import com.delhiair.watch.core.fixed
import com.delhiair.watch.core.spokenSummary
import com.delhiair.watch.core.verdictFor

data class VerdictStyle(val verdict: Verdict, val color: Color, val icon: Int)

fun verdictStyle(window: Window, request: PlanRequest): VerdictStyle {
    val verdict = verdictFor(window, request)
    val icon = when (verdict) {
        Verdict.RAIN -> R.drawable.ic_rain
        Verdict.HEAT -> R.drawable.ic_sun
        else -> when (request.activity) {
            Outing.RUN -> R.drawable.ic_run
            Outing.CYCLE -> R.drawable.ic_bike
            Outing.KIDS -> R.drawable.ic_kids
            Outing.COMMUTE -> R.drawable.ic_commute
            Outing.WALK -> R.drawable.ic_walk
        }
    }
    return VerdictStyle(verdict, aqiColor(window.maxAqi), icon)
}

/** One glance: should I go, where, when, and the three numbers that decide it. */
@Composable
fun WindowScreen(
    state: AirUiState,
    selected: Int,
    onSelect: (Int) -> Unit,
    onDetails: () -> Unit,
    onRemind: (com.delhiair.watch.core.Recommendation) -> Unit,
    onNotice: (String) -> Unit,
    onDismissMessage: () -> Unit,
) {
    val recommendation = state.recommendation
    if (recommendation == null) {
        Scroller { item { Centered("No window selected.") } }
        return
    }
    val windows = listOf(recommendation.window) + recommendation.backups
    val index = selected.coerceAtMost(windows.lastIndex)
    val window = windows[index]
    val shown = recommendation.copy(window = window)
    val timezone = recommendation.forecast.timezone
    val style = verdictStyle(window, recommendation.request)
    val found = recommendation.search
    val advice = recommendation.suggestion
    val context = LocalContext.current
    var speech by remember { mutableStateOf<TextToSpeech?>(null) }
    var speechFailed by remember { mutableStateOf(false) }
    val notifications = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) onRemind(shown) else onNotice("Notifications are off, so no reminder was set.")
    }
    DisposableEffect(Unit) { onDispose { speech?.shutdown() } }
    val remind = {
        val needed = Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
        val allowed = ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED
        if (needed && !allowed) notifications.launch(Manifest.permission.POST_NOTIFICATIONS) else onRemind(shown)
    }
    val readAloud = {
        val text = com.delhiair.watch.core.spokenSummary(shown)
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
        Unit
    }
    Scroller {
        item { Box(Modifier.height(2.dp)) }
        item { Pill(advice?.label ?: style.verdict.label, style.color, style.icon) }
        if (advice != null && advice.headline != advice.label) {
            item {
                Text(
                    advice.headline,
                    color = Paper,
                    fontSize = 19.sp,
                    fontWeight = FontWeight.Bold,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }
        if (found != null) {
            item {
                Text(
                    found.place,
                    color = Paper,
                    fontSize = 21.sp,
                    fontWeight = FontWeight.Bold,
                    textAlign = TextAlign.Center,
                    lineHeight = 24.sp,
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp),
                )
            }
            item {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(3.dp)) {
                    SmallIcon(R.drawable.ic_pin, Sky, 13.dp)
                    Text(
                        if (found.distanceKm < 0.1) found.area else "${fixed(found.distanceKm, 1)} km · ${found.area}",
                        color = Sky,
                        fontSize = 13.sp,
                        maxLines = 1,
                    )
                }
            }
        }
        item {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    "${clock(window.start, timezone)}–${clock(window.end, timezone)}",
                    color = Sun,
                    fontSize = 28.sp,
                    fontWeight = FontWeight.Black,
                    maxLines = 1,
                )
                Text(
                    dayLabel(window.start, timezone) + if (index > 0) " · backup $index" else "",
                    color = Muted,
                    fontSize = 13.sp,
                )
            }
        }
        item {
            Panel {
                Row(horizontalArrangement = Arrangement.SpaceEvenly, modifier = Modifier.fillMaxWidth()) {
                    Stat(R.drawable.ic_air, fixed(window.usAqi, 0), "AQI", aqiColor(window.maxAqi), Modifier.weight(1f))
                    Stat(R.drawable.ic_rain, "${fixed(window.rain, 0)}%", "Rain", Sky, Modifier.weight(1f))
                    Stat(R.drawable.ic_heat, "${fixed(window.temperature, 0)}°", "Heat", Paper, Modifier.weight(1f))
                }
            }
        }
        if (advice != null) {
            item { SectionTitle("Why") }
            item {
                Panel {
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        advice.reasons.forEach { Bullet(it, Sun) }
                    }
                }
            }
        }
        found?.measuredAqi?.let { measured ->
            item {
                Pill("Monitor now $measured", aqiColor(measured.toDouble()), filled = false)
            }
        }
        state.message?.let { message ->
            item {
                Card(onClick = onDismissMessage, modifier = Modifier.fillMaxWidth()) {
                    Text(message, fontSize = 13.sp, color = Sun)
                }
            }
        }
        item {
            Row(horizontalArrangement = Arrangement.SpaceEvenly, modifier = Modifier.fillMaxWidth().padding(top = 2.dp)) {
                RoundAction(R.drawable.ic_bell, "Remind", remind)
                RoundAction(R.drawable.ic_speak, "Read", readAloud)
                RoundAction(R.drawable.ic_details, "Details", onDetails)
            }
        }
        if (speechFailed) item { Centered("No speech engine on this watch.", color = Sun, size = 12) }
        if (windows.size > 1) {
            item { SectionTitle("Other times") }
            windows.indices.filter { it != index }.forEach { other ->
                item {
                    MenuRow(
                        R.drawable.ic_refresh,
                        "${clock(windows[other].start, timezone)}–${clock(windows[other].end, timezone)}",
                        "${dayLabel(windows[other].start, timezone)} · AQI ${fixed(windows[other].usAqi, 0)}",
                    ) { onSelect(other) }
                }
            }
        }
        if (found != null && found.others.isNotEmpty()) {
            item { SectionTitle("Other places") }
            found.others.forEach { other ->
                item {
                    Panel {
                        Column {
                            Text(other.place, fontSize = 14.sp, color = Paper, fontWeight = FontWeight.SemiBold, maxLines = 2)
                            Text("${fixed(other.distanceKm, 1)} km · ${other.time}", fontSize = 12.sp, color = Muted, maxLines = 1)
                            Text(
                                "AQI ${other.aqi}" + (other.measured?.let { " · monitor $it" } ?: ""),
                                fontSize = 13.sp,
                                color = aqiColor((other.measured ?: other.aqi).toDouble()),
                            )
                        }
                    }
                }
            }
        }
        if (state.fromAgent) {
            item { Centered("From the Delhi Air agent", color = Sky, size = 11) }
            state.heard?.let { words -> item { Centered("You said: $words", color = Muted, size = 11) } }
        }
        item { Box(Modifier.height(24.dp)) }
    }
}

@Composable
private fun Fact(label: String, value: String) {
    Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
        Text(label, fontSize = 13.sp, color = Muted)
        Text(value, fontSize = 13.sp, color = Paper, fontWeight = FontWeight.SemiBold, textAlign = TextAlign.End)
    }
}

/** Everything behind the decision, for anyone who wants it. */
@Composable
fun DetailsScreen(state: AirUiState, selected: Int) {
    val recommendation = state.recommendation
    if (recommendation == null) {
        Scroller { item { Centered("No window selected.") } }
        return
    }
    val windows = listOf(recommendation.window) + recommendation.backups
    val window = windows[selected.coerceAtMost(windows.lastIndex)]
    val result = assess(window, recommendation.request)
    val found = recommendation.search
    Scroller {
        item { SectionTitle("Why this") }
        if (found != null) {
            item { Centered(found.why, size = 14) }
            item {
                Centered("Compared ${found.checked} of ${found.searched} places near ${found.area}.", color = Muted, size = 12)
            }
        }
        item { Centered(result.verdict, color = Sun, size = 13) }
        item { SectionTitle("Conditions") }
        item {
            Panel {
                Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    Fact("Average AQI", fixed(window.usAqi, 0))
                    Fact("Worst hour", fixed(window.maxAqi, 0))
                    Fact("PM2.5", "${fixed(window.pm25, 0)} µg/m³")
                    Fact("Rain", "${fixed(window.rain, 0)}%")
                    Fact("Temperature", "${fixed(window.temperature, 0)}°C")
                    window.apparent?.let { Fact("Feels like", "${fixed(it, 0)}°C") }
                    window.uv?.let { Fact("UV", fixed(it, 1)) }
                    window.wind?.let { Fact("Wind", "${fixed(it, 0)} km/h") }
                    Fact(
                        "Daylight",
                        when (window.daylight) {
                            true -> "Yes"
                            false -> "Partly"
                            null -> "Unknown"
                        },
                    )
                }
            }
        }
        val tips = result.checklist.drop(2)
        if (tips.isNotEmpty()) {
            item { SectionTitle("Before you go") }
            item {
                Panel {
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) { tips.forEach { Bullet(it, Sun) } }
                }
            }
        }
        if (result.warnings.isNotEmpty()) {
            item { SectionTitle("Worth knowing") }
            item {
                Panel {
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) { result.warnings.forEach { Bullet(it) } }
                }
            }
        }
        item { Box(Modifier.height(24.dp)) }
    }
}
