package com.delhiair.watch.ui

import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.wear.compose.material3.ColorScheme
import androidx.wear.compose.material3.MaterialTheme

val Sun = Color(0xFFFFE62B)
val Ink = Color(0xFF080B0D)
val Sky = Color(0xFF8BE9ED)
val Paper = Color(0xFFFFF7EF)
val Muted = Color(0xFFB9B4AE)
val Panel = Color(0xFF1C2024)

/** The same AQI scale as the website. */
fun aqiColor(aqi: Double): Color = when {
    aqi <= 50 -> Color(0xFF7CFF5B)
    aqi <= 100 -> Color(0xFFFFE62B)
    aqi <= 150 -> Color(0xFFFF6A2A)
    aqi <= 200 -> Color(0xFFFF3B4A)
    aqi <= 300 -> Color(0xFFC77DFF)
    else -> Color(0xFFE5484D)
}

private val Scheme = ColorScheme(
    primary = Sun,
    onPrimary = Ink,
    primaryContainer = Panel,
    onPrimaryContainer = Paper,
    secondary = Sky,
    onSecondary = Ink,
    surfaceContainer = Panel,
    onSurface = Paper,
    onSurfaceVariant = Muted,
    background = Color.Black,
    onBackground = Paper,
)

@Composable
fun DelhiAirTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = Scheme, content = content)
}
