package com.delhiair.watch.tile

import androidx.concurrent.futures.ResolvableFuture
import androidx.wear.protolayout.ActionBuilders
import androidx.wear.protolayout.ColorBuilders.argb
import androidx.wear.protolayout.DimensionBuilders
import androidx.wear.protolayout.DimensionBuilders.dp
import androidx.wear.protolayout.DimensionBuilders.expand
import androidx.wear.protolayout.DimensionBuilders.sp
import androidx.wear.protolayout.LayoutElementBuilders
import androidx.wear.protolayout.LayoutElementBuilders.Column
import androidx.wear.protolayout.LayoutElementBuilders.FontStyle
import androidx.wear.protolayout.LayoutElementBuilders.Layout
import androidx.wear.protolayout.LayoutElementBuilders.Text
import androidx.wear.protolayout.ModifiersBuilders
import androidx.wear.protolayout.ResourceBuilders
import androidx.wear.protolayout.TimelineBuilders
import androidx.wear.tiles.RequestBuilders
import androidx.wear.tiles.TileBuilders
import androidx.wear.tiles.TileService
import com.delhiair.watch.core.AirException
import com.delhiair.watch.core.PlanRequest
import com.delhiair.watch.core.aqiCategory
import com.delhiair.watch.core.clock
import com.delhiair.watch.core.dayLabel
import com.delhiair.watch.core.fixed
import com.delhiair.watch.core.recommend
import com.delhiair.watch.data.AirRepository
import com.delhiair.watch.data.HabitStore
import com.delhiair.watch.data.Snapshot
import com.delhiair.watch.data.headlineAqi
import com.delhiair.watch.data.localStation
import com.delhiair.watch.data.nowSeconds
import com.google.common.util.concurrent.ListenableFuture

private const val RESOURCES_VERSION = "1"
private const val FRESHNESS_MS = 30 * 60 * 1000L

private fun colorFor(aqi: Double): Int = when {
    aqi <= 50 -> 0xFF7CFF5B.toInt()
    aqi <= 100 -> 0xFFFFE62B.toInt()
    aqi <= 150 -> 0xFFFF6A2A.toInt()
    aqi <= 200 -> 0xFFFF3B4A.toInt()
    aqi <= 300 -> 0xFFC77DFF.toInt()
    else -> 0xFFE5484D.toInt()
}

private fun label(value: String, size: Float, color: Int, bold: Boolean = false) = Text.Builder()
    .setText(value)
    .setMaxLines(2)
    .setFontStyle(
        FontStyle.Builder()
            .setSize(sp(size))
            .setColor(argb(color))
            .setWeight(
                if (bold) LayoutElementBuilders.FONT_WEIGHT_BOLD else LayoutElementBuilders.FONT_WEIGHT_NORMAL,
            )
            .build(),
    )
    .build()

/** The app's ring: a 270 degree scale opening at the bottom, anchored at its start. */
private fun ring(sweep: Float, color: Int) = LayoutElementBuilders.Arc.Builder()
    .setAnchorAngle(DimensionBuilders.degrees(225f))
    .setAnchorType(LayoutElementBuilders.ARC_ANCHOR_START)
    .addContent(
        LayoutElementBuilders.ArcLine.Builder()
            .setLength(DimensionBuilders.degrees(sweep))
            .setThickness(dp(7f))
            .setColor(argb(color))
            .build(),
    )
    .build()

/** The glanceable summary: current air, then the next window worth planning around. */
class AirTileService : TileService() {
    private fun bestLine(snapshot: Snapshot, request: PlanRequest): Pair<String, String> = try {
        val window = recommend(request, snapshot.location, snapshot.forecast, nowSeconds()).window
        val timezone = snapshot.forecast.timezone
        val prefix = if (window.maxAqi > 100) "Least-bad" else "Best"
        "$prefix ${clock(window.start, timezone)}–${clock(window.end, timezone)}" to
            "${dayLabel(window.start, timezone)} · AQI ${fixed(window.usAqi, 0)}"
    } catch (_: AirException) {
        "No window fits" to "Open to adjust"
    }

    private fun content(): LayoutElementBuilders.LayoutElement {
        val repository = AirRepository(this)
        val request = repository.loadRequest()
        val snapshot = repository.surfaceSnapshot(request)
        val aqi = snapshot?.headlineAqi
        val column = Column.Builder()
        if (snapshot == null || aqi == null) {
            column.addContent(label("Delhi Air", 16f, 0xFFFFE62B.toInt(), bold = true))
            column.addContent(label("Tap to refresh", 13f, 0xFFFFF7EF.toInt()))
        } else {
                val agent = HabitStore(this).surface.split("\n")
            val fresh = agent.size == 3 && nowSeconds() - (agent[2].toLongOrNull() ?: 0) < 3 * 3600
            val (best, detail) = if (fresh) agent[0] to agent[1] else bestLine(snapshot, request)
            val source = if (snapshot.localStation != null) "Station" else "Model"
            column.addContent(label(snapshot.location.name.substringBefore(","), 13f, 0xFF8BE9ED.toInt()))
            column.addContent(label(fixed(aqi, 0), 42f, colorFor(aqi), bold = true))
            column.addContent(label("${aqiCategory(aqi)} · $source", 12f, colorFor(aqi)))
            column.addContent(LayoutElementBuilders.Spacer.Builder().setHeight(dp(6f)).build())
            column.addContent(label(best, 14f, 0xFFFFF7EF.toInt(), bold = true))
            column.addContent(label(detail, 12f, 0xFFB9B4AE.toInt()))
            val age = (nowSeconds() - snapshot.forecast.fetchedAt) / 3600
            if (age >= 1) column.addContent(label("Updated $age h ago", 12f, 0xFFFFE62B.toInt()))
        }
        val open = ModifiersBuilders.Clickable.Builder()
            .setId("open")
            .setOnClick(
                ActionBuilders.LaunchAction.Builder()
                    .setAndroidActivity(
                        ActionBuilders.AndroidActivity.Builder()
                            .setPackageName(packageName)
                            .setClassName("com.delhiair.watch.ui.MainActivity")
                            .build(),
                    )
                    .build(),
            )
            .build()
        val box = LayoutElementBuilders.Box.Builder()
            .setWidth(expand())
            .setHeight(expand())
            .setModifiers(ModifiersBuilders.Modifiers.Builder().setClickable(open).build())
        if (aqi != null) {
            box.addContent(ring(360f * 0.75f, 0x1FFFFFFF))
            box.addContent(ring((270f * (aqi / 500.0).coerceIn(0.02, 1.0)).toFloat(), colorFor(aqi)))
        }
        return box.addContent(column.build()).build()
    }

    override fun onTileRequest(requestParams: RequestBuilders.TileRequest): ListenableFuture<TileBuilders.Tile> {
        val tile = TileBuilders.Tile.Builder()
            .setResourcesVersion(RESOURCES_VERSION)
            .setFreshnessIntervalMillis(FRESHNESS_MS)
            .setTileTimeline(TimelineBuilders.Timeline.fromLayoutElement(content()))
            .build()
        return ResolvableFuture.create<TileBuilders.Tile>().apply { set(tile) }
    }

    override fun onTileResourcesRequest(
        requestParams: RequestBuilders.ResourcesRequest,
    ): ListenableFuture<ResourceBuilders.Resources> =
        ResolvableFuture.create<ResourceBuilders.Resources>().apply {
            set(ResourceBuilders.Resources.Builder().setVersion(RESOURCES_VERSION).build())
        }
}
