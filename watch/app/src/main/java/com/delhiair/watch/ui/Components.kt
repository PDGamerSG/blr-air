package com.delhiair.watch.ui

import androidx.annotation.DrawableRes
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.wear.compose.material3.FilledTonalButton
import androidx.wear.compose.material3.FilledTonalIconButton
import androidx.wear.compose.material3.Icon
import androidx.wear.compose.material3.ScreenScaffold
import androidx.wear.compose.material3.Text

/** A plain scrolling page. Round-screen insets come from the scaffold and the side padding. */
@Composable
fun Scroller(
    edgeButton: (@Composable BoxScope.() -> Unit)? = null,
    listState: LazyListState = rememberLazyListState(),
    content: LazyListScope.() -> Unit,
) {
    val list: @Composable BoxScope.(PaddingValues) -> Unit = { padding ->
        LazyColumn(
            state = listState,
            contentPadding = padding,
            verticalArrangement = Arrangement.spacedBy(8.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.fillMaxSize().padding(horizontal = 14.dp),
            content = content,
        )
    }
    if (edgeButton != null) {
        ScreenScaffold(scrollState = listState, edgeButton = edgeButton, content = list)
    } else {
        ScreenScaffold(scrollState = listState, content = list)
    }
}

@Composable
fun Centered(text: String, modifier: Modifier = Modifier, color: Color = Paper, size: Int = 13) {
    Text(
        text = text,
        color = color,
        fontSize = size.sp,
        textAlign = TextAlign.Center,
        modifier = modifier.fillMaxWidth().padding(horizontal = 6.dp),
    )
}

@Composable
fun SectionTitle(text: String) {
    Text(
        text.uppercase(),
        color = Muted,
        fontSize = 11.sp,
        fontWeight = FontWeight.SemiBold,
        letterSpacing = 1.sp,
        textAlign = TextAlign.Center,
        modifier = Modifier.fillMaxWidth().padding(top = 10.dp, bottom = 2.dp),
    )
}

@Composable
fun SmallIcon(@DrawableRes icon: Int, tint: Color, size: Dp = 16.dp) {
    Icon(painterResource(icon), contentDescription = null, tint = tint, modifier = Modifier.size(size))
}

/**
 * Follows the watch's bezel, so it must fill the whole screen: inside a padded list it
 * would sit off-centre. The scale runs to 500, so Delhi's usual readings fill most of it.
 */
@Composable
fun AqiRing(aqi: Double, modifier: Modifier = Modifier, thickness: Dp = 7.dp) {
    val color = aqiColor(aqi)
    Canvas(modifier) {
        val stroke = thickness.toPx()
        val diameter = size.minDimension - stroke - 2.dp.toPx()
        val arc = Size(diameter, diameter)
        val origin = Offset((size.width - diameter) / 2, (size.height - diameter) / 2)
        val sweep = 270f
        drawArc(
            color = Color.White.copy(alpha = 0.10f),
            startAngle = 135f,
            sweepAngle = sweep,
            useCenter = false,
            topLeft = origin,
            size = arc,
            style = Stroke(stroke, cap = StrokeCap.Round),
        )
        drawArc(
            color = color,
            startAngle = 135f,
            sweepAngle = sweep * (aqi / 500.0).coerceIn(0.02, 1.0).toFloat(),
            useCenter = false,
            topLeft = origin,
            size = arc,
            style = Stroke(stroke, cap = StrokeCap.Round),
        )
    }
}

@Composable
fun Pill(text: String, color: Color, @DrawableRes icon: Int? = null, filled: Boolean = true) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(5.dp),
        modifier = Modifier
            .clip(RoundedCornerShape(50))
            .background(if (filled) color else color.copy(alpha = 0.16f))
            .padding(horizontal = 12.dp, vertical = 5.dp),
    ) {
        val ink = if (filled) Ink else color
        if (icon != null) SmallIcon(icon, ink, 14.dp)
        Text(text, color = ink, fontSize = 13.sp, fontWeight = FontWeight.Bold, maxLines = 1)
    }
}

@Composable
fun Stat(@DrawableRes icon: Int, value: String, label: String, color: Color, modifier: Modifier = Modifier) {
    Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = modifier) {
        SmallIcon(icon, color, 16.dp)
        Text(value, color = color, fontSize = 17.sp, fontWeight = FontWeight.Bold, maxLines = 1)
        Text(label, color = Muted, fontSize = 10.sp, maxLines = 1)
    }
}

@Composable
fun RoundAction(
    @DrawableRes icon: Int,
    label: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = modifier) {
        FilledTonalIconButton(onClick = onClick, enabled = enabled, modifier = Modifier.size(52.dp)) {
            Icon(painterResource(icon), contentDescription = label, modifier = Modifier.size(24.dp))
        }
        Text(label, color = Paper, fontSize = 11.sp, maxLines = 1, modifier = Modifier.padding(top = 3.dp))
    }
}

@Composable
fun MenuRow(
    @DrawableRes icon: Int,
    title: String,
    subtitle: String? = null,
    enabled: Boolean = true,
    onClick: () -> Unit,
) {
    FilledTonalButton(
        onClick = onClick,
        enabled = enabled,
        icon = { Icon(painterResource(icon), contentDescription = null, modifier = Modifier.size(22.dp)) },
        label = { Text(title, maxLines = 1, overflow = TextOverflow.Ellipsis) },
        secondaryLabel = subtitle?.let { { Text(it, maxLines = 1, overflow = TextOverflow.Ellipsis) } },
        modifier = Modifier.fillMaxWidth(),
    )
}

/** A quiet surface for grouped information. */
@Composable
fun Panel(modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    Box(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(22.dp))
            .background(Panel)
            .padding(horizontal = 14.dp, vertical = 10.dp),
    ) {
        content()
    }
}

@Composable
fun Bullet(text: String, color: Color = Sky) {
    Row(modifier = Modifier.fillMaxWidth().padding(horizontal = 6.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Box(
            Modifier
                .padding(top = 6.dp)
                .size(6.dp)
                .clip(CircleShape)
                .background(color),
        )
        Text(text, color = Paper, fontSize = 13.sp)
    }
}
