package com.delhiair.watch.work

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import androidx.wear.tiles.TileService
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceUpdateRequester
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.Data
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.delhiair.watch.R
import com.delhiair.watch.complication.AqiComplicationService
import com.delhiair.watch.core.AirException
import com.delhiair.watch.core.Recommendation
import com.delhiair.watch.core.clock
import com.delhiair.watch.core.Location
import com.delhiair.watch.core.fixed
import com.delhiair.watch.data.AirRepository
import com.delhiair.watch.data.nowSeconds
import com.delhiair.watch.tile.AirTileService
import com.delhiair.watch.ui.MainActivity
import java.util.concurrent.TimeUnit

/** Ask the tile and watch-face complication to redraw from the saved forecast. */
fun refreshSurfaces(context: Context) {
    TileService.getUpdater(context).requestUpdate(AirTileService::class.java)
    ComplicationDataSourceUpdateRequester
        .create(context, ComponentName(context, AqiComplicationService::class.java))
        .requestUpdateAll()
}

/** An hourly refresh keeps the tile current without draining the battery. */
class RefreshWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val repository = AirRepository(applicationContext)
        return try {
            val location = repository.resolve(repository.loadRequest().place)
            repository.snapshot(location, force = true)
            refreshSurfaces(applicationContext)
            Result.success()
        } catch (_: AirException) {
            Result.retry()
        }
    }

    companion object {
        fun schedule(context: Context) {
            val request = PeriodicWorkRequestBuilder<RefreshWorker>(1, TimeUnit.HOURS)
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .build()
            WorkManager.getInstance(context)
                .enqueueUniquePeriodicWork("refresh", ExistingPeriodicWorkPolicy.KEEP, request)
        }
    }
}

object Reminders {
    private const val CHANNEL = "recheck"
    private const val LEAD_SECONDS = 3600L

    fun schedule(context: Context, recommendation: Recommendation): String {
        val window = recommendation.window
        val timezone = recommendation.forecast.timezone
        val delay = window.start - LEAD_SECONDS - nowSeconds()
        val request = OneTimeWorkRequestBuilder<ReminderWorker>()
            .setInitialDelay(maxOf(delay, 0), TimeUnit.SECONDS)
            .setInputData(
                Data.Builder()
                    .putString("place", recommendation.location.name)
                    .putDouble("latitude", recommendation.location.latitude)
                    .putDouble("longitude", recommendation.location.longitude)
                    .putString("time", "${clock(window.start, timezone)}–${clock(window.end, timezone)}")
                    .putString("aqi", fixed(window.usAqi, 0))
                    .putLong("start", window.start)
                    .putLong("end", window.end)
                    .build(),
            )
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork("reminder", ExistingWorkPolicy.REPLACE, request)
        return if (delay > 0) {
            "Reminder set for ${clock(window.start - LEAD_SECONDS, timezone)}."
        } else {
            "Reminder set. This window starts within the hour."
        }
    }

    fun show(context: Context, title: String, text: String) {
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL, "Recheck reminders", NotificationManager.IMPORTANCE_DEFAULT),
        )
        val allowed = ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS)
        if (allowed != PackageManager.PERMISSION_GRANTED) return
        val open = PendingIntent.getActivity(
            context,
            0,
            Intent(context, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_air)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setContentIntent(open)
            .setAutoCancel(true)
            .build()
        manager.notify(1, notification)
    }
}

/** Rechecks the forecast when the reminder fires, because the saved window can go stale. */
class ReminderWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val place = inputData.getString("place").orEmpty()
        val time = inputData.getString("time").orEmpty()
        val planned = inputData.getString("aqi").orEmpty()
        val start = inputData.getLong("start", 0)
        val end = inputData.getLong("end", 0)
        val location = Location(
            place,
            inputData.getDouble("latitude", 0.0),
            inputData.getDouble("longitude", 0.0),
        )
        // Recheck the exact place and hours planned, not whatever the watch is set to now.
        val update = try {
            val snapshot = AirRepository(applicationContext).snapshot(location, force = true)
            val hours = snapshot.forecast.hours.filter { it.time in start until end }
            if (hours.isEmpty()) {
                "No fresh forecast for those hours, so check before leaving."
            } else {
                "Latest forecast for then: AQI ${fixed(hours.sumOf { it.usAqi } / hours.size, 0)}."
            }
        } catch (_: AirException) {
            "Couldn't recheck the forecast, so check it before leaving."
        }
        Reminders.show(applicationContext, "Recheck $place", "Planned $time at AQI $planned. $update")
        return Result.success()
    }
}
