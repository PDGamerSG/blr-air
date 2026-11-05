package com.delhiair.watch.ui

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.location.LocationManager
import android.os.CancellationSignal
import android.os.Handler
import android.os.Looper
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.wear.compose.material3.Button
import androidx.wear.compose.material3.CircularProgressIndicator
import androidx.wear.compose.material3.SwitchButton
import androidx.wear.compose.material3.Text
import com.delhiair.watch.R
import com.delhiair.watch.data.HabitStore
import com.delhiair.watch.core.AIR_MODEL_NOTE
import com.delhiair.watch.core.Activity
import com.delhiair.watch.core.Day
import com.delhiair.watch.core.LOCALITIES
import com.delhiair.watch.core.Period
import com.delhiair.watch.core.PlanRequest
import com.delhiair.watch.core.clock
import com.delhiair.watch.core.dayLabel
import com.delhiair.watch.core.fixed

/** Tap to step through the options; a watch has no room for a form. */
private fun <T> List<T>.after(value: T): T = this[(indexOf(value) + 1) % size]

@Composable
private fun Cycle(label: String, value: String, icon: Int = R.drawable.ic_tune, onClick: () -> Unit) {
    MenuRow(icon, label, value, onClick = onClick)
}

private fun activityIcon(activity: Activity) = when (activity) {
    Activity.RUN -> R.drawable.ic_run
    Activity.CYCLE -> R.drawable.ic_bike
    Activity.KIDS -> R.drawable.ic_kids
    Activity.COMMUTE -> R.drawable.ic_commute
    Activity.WALK -> R.drawable.ic_walk
}

@Composable
fun PlanScreen(request: PlanRequest, onChange: (PlanRequest) -> Unit, onLimits: () -> Unit) {
    Scroller {
        item { SectionTitle("Plan") }
        item {
            Cycle("Activity", request.activity.label, activityIcon(request.activity)) {
                onChange(request.copy(activity = Activity.entries.toList().after(request.activity)))
            }
        }
        item {
            Cycle("Length", "${request.hours} hour" + if (request.hours > 1) "s" else "") {
                onChange(request.copy(hours = if (request.hours == 1) 2 else 1))
            }
        }
        item {
            Cycle("Day", request.day.label) {
                onChange(request.copy(day = Day.entries.toList().after(request.day)))
            }
        }
        item {
            Cycle("Time of day", request.period.label) {
                onChange(request.copy(period = Period.entries.toList().after(request.period)))
            }
        }
        item {
            SwitchButton(
                checked = request.daylightOnly,
                onCheckedChange = { onChange(request.copy(daylightOnly = it)) },
                label = { Text("Daylight only") },
                modifier = Modifier.fillMaxWidth(),
            )
        }
        item {
            val context = LocalContext.current
            val store = remember { HabitStore(context) }
            var auto by remember { mutableStateOf(store.autoSuggestions) }
            val agentAccess = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {}
            SwitchButton(
                checked = auto,
                onCheckedChange = {
                    auto = it
                    store.autoSuggestions = it
                    val missing = AGENT_PERMISSIONS.filter { name ->
                        ContextCompat.checkSelfPermission(context, name) != PackageManager.PERMISSION_GRANTED
                    }
                    if (it && missing.isNotEmpty()) agentAccess.launch(missing.toTypedArray())
                },
                label = { Text("Agent suggestions") },
                secondaryLabel = { Text("Learns your routine") },
                modifier = Modifier.fillMaxWidth(),
            )
        }
        item {
            val count = listOf(
                request.maxAqi, request.maxRain, request.maxTemperature, request.maxUv, request.maxWind,
            ).count { it != null }
            MenuRow(R.drawable.ic_tune, "Limits", if (count == 0) "None set" else "$count set", onClick = onLimits)
        }
    }
}

private val AQI_STEPS = listOf(null, 100.0, 150.0, 200.0, 300.0)
private val RAIN_STEPS = listOf(null, 10.0, 30.0, 50.0)
private val HEAT_STEPS = listOf(null, 30.0, 35.0, 40.0)
private val UV_STEPS = listOf(null, 3.0, 5.0, 8.0)
private val WIND_STEPS = listOf(null, 10.0, 20.0, 30.0)

private fun show(value: Double?, unit: String) =
    if (value == null) "Off" else "At most ${fixed(value, 0)}$unit"

@Composable
fun LimitsScreen(request: PlanRequest, onChange: (PlanRequest) -> Unit) {
    Scroller {
        item { SectionTitle("Limits") }
        item { Centered("Every hour must pass. Limits are never relaxed.", color = Muted, size = 12) }
        item {
            Cycle("US AQI", show(request.maxAqi, ""), R.drawable.ic_air) {
                onChange(request.copy(maxAqi = AQI_STEPS.after(request.maxAqi)))
            }
        }
        item {
            Cycle("Rain chance", show(request.maxRain, "%"), R.drawable.ic_rain) {
                onChange(request.copy(maxRain = RAIN_STEPS.after(request.maxRain)))
            }
        }
        item {
            Cycle("Feels like", show(request.maxTemperature, "°C"), R.drawable.ic_heat) {
                onChange(request.copy(maxTemperature = HEAT_STEPS.after(request.maxTemperature)))
            }
        }
        item {
            Cycle("UV index", show(request.maxUv, ""), R.drawable.ic_sun) {
                onChange(request.copy(maxUv = UV_STEPS.after(request.maxUv)))
            }
        }
        item {
            Cycle("Wind", show(request.maxWind, " km/h"), R.drawable.ic_air) {
                onChange(request.copy(maxWind = WIND_STEPS.after(request.maxWind)))
            }
        }
    }
}

/** Watches differ in which provider has a fix, so a recent one wins, then each is tried in turn. */
@SuppressLint("MissingPermission")
private fun currentLocation(context: Context, onResult: (Double, Double) -> Unit, onFail: () -> Unit) {
    val manager = context.getSystemService(LocationManager::class.java)
    val providers = listOf(LocationManager.FUSED_PROVIDER, LocationManager.NETWORK_PROVIDER, LocationManager.GPS_PROVIDER)
        .filter { it in manager.allProviders && manager.isProviderEnabled(it) }
    val recent = providers.mapNotNull { manager.getLastKnownLocation(it) }
        .filter { System.currentTimeMillis() - it.time < 30 * 60 * 1000L }
        .maxByOrNull { it.time }
    if (recent != null) {
        onResult(recent.latitude, recent.longitude)
        return
    }
    val handler = Handler(Looper.getMainLooper())
    fun attempt(index: Int) {
        if (index >= providers.size) {
            onFail()
            return
        }
        val signal = CancellationSignal()
        var finished = false
        val giveUp = Runnable {
            if (!finished) {
                finished = true
                signal.cancel()
                attempt(index + 1)
            }
        }
        handler.postDelayed(giveUp, 12_000)
        manager.getCurrentLocation(providers[index], signal, ContextCompat.getMainExecutor(context)) { location ->
            if (!finished) {
                finished = true
                handler.removeCallbacks(giveUp)
                if (location != null) onResult(location.latitude, location.longitude) else attempt(index + 1)
            }
        }
    }
    attempt(0)
}

@Composable
fun PlacesScreen(
    selected: String,
    onPick: (String) -> Unit,
    onCoordinates: (Double, Double) -> Unit,
) {
    val context = LocalContext.current
    var status by remember { mutableStateOf<String?>(null) }
    // A fix can take half a minute; it must not act on a screen the user has left.
    var active by remember { mutableStateOf(true) }
    DisposableEffect(Unit) { onDispose { active = false } }
    val locate = {
        status = "Finding you…"
        currentLocation(
            context,
            { latitude, longitude -> if (active) onCoordinates(latitude, longitude) },
        ) { status = "Location unavailable. Pick a place below." }
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) locate() else status = "Location permission is off."
    }
    Scroller {
        item { SectionTitle("Place") }
        item {
            Button(
                icon = { SmallIcon(R.drawable.ic_locate, Ink, 22.dp) },
                onClick = {
                    val state = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION)
                    if (state == PackageManager.PERMISSION_GRANTED) {
                        locate()
                    } else {
                        permission.launch(Manifest.permission.ACCESS_COARSE_LOCATION)
                    }
                },
                label = { Text("Use my location") },
                secondaryLabel = status?.let { { Text(it) } },
                modifier = Modifier.fillMaxWidth(),
            )
        }
        items(LOCALITIES.size) { index ->
            val locality = LOCALITIES[index]
            MenuRow(
                R.drawable.ic_pin,
                locality.name,
                if (locality.name.equals(selected, true)) "Selected" else null,
            ) { onPick(locality.name) }
        }
    }
}

@Composable
fun ComparePickScreen(onCompare: (List<String>) -> Unit) {
    val picked = remember { mutableStateListOf<String>() }
    Scroller {
        item { SectionTitle("Pick 2 or 3") }
        item {
            Button(
                onClick = { onCompare(picked.toList()) },
                enabled = picked.size >= 2,
                label = { Text("Compare ${picked.size}") },
                modifier = Modifier.fillMaxWidth(),
            )
        }
        items(LOCALITIES.size) { index ->
            val name = LOCALITIES[index].name
            SwitchButton(
                checked = name in picked,
                onCheckedChange = { on ->
                    if (!on) picked.remove(name) else if (picked.size < 3) picked.add(name)
                },
                label = { Text(name) },
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

@Composable
fun CompareScreen(state: AirUiState) {
    val comparison = state.comparison
    Scroller {
        item { SectionTitle("Compare") }
        if (state.comparing || comparison == null) {
            item { CircularProgressIndicator(modifier = Modifier.padding(16.dp).size(48.dp)) }
            return@Scroller
        }
        comparison.cleanerNow?.let { place ->
            item {
                Panel {
                    Centered(
                        "Monitors show $place is cleaner right now. The ranking is forecast only.",
                        color = Sun,
                    )
                }
            }
        }
        comparison.sharedAirModel.forEach { names ->
            item {
                Centered(
                    "${names.joinToString(" and ") { it.substringBefore(",") }} share one forecast cell.",
                    color = Muted,
                    size = 12,
                )
            }
        }
        if (comparison.tiedPlaces.isNotEmpty()) {
            item { Centered("Forecast tie. Your order breaks it.", color = Muted, size = 12) }
        }
        comparison.items.forEachIndexed { index, entry ->
            item {
                val recommendation = entry.recommendation
                Panel {
                    if (recommendation == null) {
                        Column {
                            Text(entry.place, fontSize = 15.sp, color = Paper, fontWeight = FontWeight.Bold)
                            Text("Unavailable: ${entry.error}", fontSize = 12.sp, color = Sun)
                        }
                    } else {
                        val window = recommendation.window
                        val timezone = recommendation.forecast.timezone
                        val shownAqi = entry.measuredAqi ?: window.usAqi
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            Box(
                                contentAlignment = Alignment.Center,
                                modifier = Modifier.size(30.dp).clip(CircleShape)
                                    .background(if (index == 0) Sun else Color.White.copy(alpha = 0.14f)),
                            ) {
                                Text("${index + 1}", color = if (index == 0) Ink else Paper, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                            }
                            Column(modifier = Modifier.weight(1f)) {
                                Text(entry.place.substringBefore(","), fontSize = 15.sp, color = Paper, fontWeight = FontWeight.Bold, maxLines = 1)
                                Text(
                                    "${dayLabel(window.start, timezone)} · ${clock(window.start, timezone)}",
                                    fontSize = 12.sp,
                                    color = Muted,
                                    maxLines = 1,
                                )
                                Text(
                                    "AQI ${fixed(window.usAqi, 0)}" + (entry.measuredAqi?.let { " · now ${fixed(it, 0)}" } ?: ""),
                                    fontSize = 13.sp,
                                    color = aqiColor(shownAqi),
                                    fontWeight = FontWeight.SemiBold,
                                    maxLines = 1,
                                )
                            }
                        }
                    }
                }
            }
        }
        item { Centered(AIR_MODEL_NOTE, color = Muted, size = 11) }
        item { Box(Modifier.height(24.dp)) }
    }
}
