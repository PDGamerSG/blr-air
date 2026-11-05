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
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.wear.compose.material3.Button
import androidx.wear.compose.material3.Card
import androidx.wear.compose.material3.CircularProgressIndicator
import androidx.wear.compose.material3.FilledTonalButton
import androidx.wear.compose.material3.ListHeader
import androidx.wear.compose.material3.SwitchButton
import androidx.wear.compose.material3.Text
import com.delhiair.watch.core.AIR_MODEL_NOTE
import com.delhiair.watch.core.Activity
import com.delhiair.watch.core.Day
import com.delhiair.watch.core.LOCALITIES
import com.delhiair.watch.core.Period
import com.delhiair.watch.core.PlanRequest
import com.delhiair.watch.core.fixed
import com.delhiair.watch.core.windowLabel

/** Tap to step through the options; a watch has no room for a form. */
private fun <T> List<T>.after(value: T): T = this[(indexOf(value) + 1) % size]

@Composable
private fun Cycle(label: String, value: String, onClick: () -> Unit) {
    FilledTonalButton(
        onClick = onClick,
        label = { Text(label) },
        secondaryLabel = { Text(value) },
        modifier = Modifier.fillMaxWidth(),
    )
}

@Composable
fun PlanScreen(request: PlanRequest, onChange: (PlanRequest) -> Unit, onLimits: () -> Unit) {
    Scroller {
        item { ListHeader { Text("Plan") } }
        item {
            Cycle("Activity", request.activity.label) {
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
            val count = listOf(
                request.maxAqi, request.maxRain, request.maxTemperature, request.maxUv, request.maxWind,
            ).count { it != null }
            FilledTonalButton(
                onClick = onLimits,
                label = { Text("Limits") },
                secondaryLabel = { Text(if (count == 0) "None set" else "$count set") },
                modifier = Modifier.fillMaxWidth(),
            )
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
        item { ListHeader { Text("Limits") } }
        item { Centered("Every hour must pass. Limits are never relaxed.", color = Muted, size = 12) }
        item {
            Cycle("US AQI", show(request.maxAqi, "")) {
                onChange(request.copy(maxAqi = AQI_STEPS.after(request.maxAqi)))
            }
        }
        item {
            Cycle("Rain chance", show(request.maxRain, "%")) {
                onChange(request.copy(maxRain = RAIN_STEPS.after(request.maxRain)))
            }
        }
        item {
            Cycle("Feels like", show(request.maxTemperature, "°C")) {
                onChange(request.copy(maxTemperature = HEAT_STEPS.after(request.maxTemperature)))
            }
        }
        item {
            Cycle("UV index", show(request.maxUv, "")) {
                onChange(request.copy(maxUv = UV_STEPS.after(request.maxUv)))
            }
        }
        item {
            Cycle("Wind", show(request.maxWind, " km/h")) {
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
        item { ListHeader { Text("Place") } }
        item {
            Button(
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
            FilledTonalButton(
                onClick = { onPick(locality.name) },
                label = { Text(locality.name) },
                secondaryLabel = if (locality.name.equals(selected, true)) ({ Text("Selected") }) else null,
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

@Composable
fun ComparePickScreen(onCompare: (List<String>) -> Unit) {
    val picked = remember { mutableStateListOf<String>() }
    Scroller {
        item { ListHeader { Text("Pick 2 or 3") } }
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
        item { ListHeader { Text("Compare") } }
        if (state.comparing || comparison == null) {
            item { CircularProgressIndicator(modifier = Modifier.padding(16.dp)) }
            return@Scroller
        }
        comparison.cleanerNow?.let { place ->
            item {
                Centered(
                    "Monitors show $place is cleaner right now than ${comparison.winner}. " +
                        "The ranking below is forecast only.",
                    color = Sun,
                    size = 12,
                )
            }
        }
        comparison.sharedAirModel.forEach { names ->
            item {
                Centered(
                    "Same air forecast: ${names.joinToString(" and ") { it.substringBefore(",") }} share one " +
                        "model cell, so it can't say which is cleaner.",
                    color = Sun,
                    size = 12,
                )
            }
        }
        if (comparison.tiedPlaces.isNotEmpty()) {
            item { Centered("Forecast score tie. Your order breaks it.", color = Sun, size = 12) }
        }
        comparison.items.forEachIndexed { index, entry ->
            item {
                val recommendation = entry.recommendation
                Card(onClick = {}, modifier = Modifier.fillMaxWidth()) {
                    if (recommendation == null) {
                        Text(entry.place, fontSize = 14.sp, color = Paper)
                        Text("Unavailable: ${entry.error}", fontSize = 12.sp, color = Sun)
                    } else {
                        val window = recommendation.window
                        Text("${index + 1}. ${entry.place}", fontSize = 14.sp, color = Paper)
                        Text(windowLabel(window, recommendation.forecast.timezone), fontSize = 12.sp, color = Muted)
                        Text(
                            "AQI ${fixed(window.usAqi, 0)} · PM2.5 ${fixed(window.pm25, 0)}",
                            fontSize = 13.sp,
                            color = aqiColor(window.maxAqi),
                        )
                        entry.measuredAqi?.let {
                            Text("Measured now ${fixed(it, 0)}", fontSize = 12.sp, color = aqiColor(it))
                        }
                    }
                }
            }
        }
        item { Centered(AIR_MODEL_NOTE, color = Muted, size = 12) }
    }
}
