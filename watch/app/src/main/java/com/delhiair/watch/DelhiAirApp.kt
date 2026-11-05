package com.delhiair.watch

import android.app.Application
import com.delhiair.watch.work.RefreshWorker

class DelhiAirApp : Application() {
    override fun onCreate() {
        super.onCreate()
        RefreshWorker.schedule(this)
    }
}
