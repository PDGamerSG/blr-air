package com.delhiair.watch.complication

import android.app.PendingIntent
import android.content.Intent
import androidx.wear.watchface.complications.data.ComplicationData
import androidx.wear.watchface.complications.data.ComplicationType
import androidx.wear.watchface.complications.data.LongTextComplicationData
import androidx.wear.watchface.complications.data.NoDataComplicationData
import androidx.wear.watchface.complications.data.PlainComplicationText
import androidx.wear.watchface.complications.data.RangedValueComplicationData
import androidx.wear.watchface.complications.data.ShortTextComplicationData
import androidx.wear.watchface.complications.datasource.ComplicationRequest
import androidx.wear.watchface.complications.datasource.SuspendingComplicationDataSourceService
import com.delhiair.watch.core.aqiCategory
import com.delhiair.watch.core.fixed
import com.delhiair.watch.data.AirRepository
import com.delhiair.watch.data.headlineAqi
import com.delhiair.watch.ui.MainActivity

/** Shows a saved value only; a complication must never pretend to be live when it is not. */
class AqiComplicationService : SuspendingComplicationDataSourceService() {
    private fun text(value: String) = PlainComplicationText.Builder(value).build()

    private fun build(type: ComplicationType, aqi: Double?, place: String): ComplicationData? {
        val value = aqi?.let { fixed(it, 0) } ?: "--"
        val category = aqi?.let(::aqiCategory) ?: "No data"
        val description = text("US AQI $value, $category")
        val open = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE,
        )
        return when (type) {
            ComplicationType.SHORT_TEXT ->
                ShortTextComplicationData.Builder(text(value), description)
                    .setTitle(text("AQI"))
                    .setTapAction(open)
                    .build()
            ComplicationType.LONG_TEXT ->
                LongTextComplicationData.Builder(text("AQI $value · $category"), description)
                    .setTitle(text(place))
                    .setTapAction(open)
                    .build()
            ComplicationType.RANGED_VALUE ->
                RangedValueComplicationData.Builder(
                    value = (aqi ?: 0.0).toFloat().coerceIn(0f, 500f),
                    min = 0f,
                    max = 500f,
                    contentDescription = description,
                )
                    .setText(text(value))
                    .setTitle(text("AQI"))
                    .setTapAction(open)
                    .build()
            else -> null
        }
    }

    override fun getPreviewData(type: ComplicationType): ComplicationData? = build(type, 211.0, "Delhi")

    override suspend fun onComplicationRequest(request: ComplicationRequest): ComplicationData? {
        val snapshot = AirRepository(this).surfaceSnapshot()
        val aqi = snapshot?.headlineAqi
            // A gauge at zero would read as clean air, so old data shows as no data.
            ?: return NoDataComplicationData()
        return build(request.complicationType, aqi, snapshot.location.name.substringBefore(","))
    }
}
