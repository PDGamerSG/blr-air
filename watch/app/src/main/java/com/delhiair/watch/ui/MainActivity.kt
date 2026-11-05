package com.delhiair.watch.ui

import android.Manifest
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.wear.compose.material3.AppScaffold
import androidx.wear.compose.navigation.SwipeDismissableNavHost
import androidx.wear.compose.navigation.composable
import androidx.wear.compose.navigation.rememberSwipeDismissableNavController
import com.delhiair.watch.data.HabitStore

object Routes {
    const val HOME = "home"
    const val WINDOW = "window"
    const val PLAN = "plan"
    const val LIMITS = "limits"
    const val PLACES = "places"
    const val COMPARE_PICK = "compare-pick"
    const val COMPARE = "compare"
    const val ABOUT = "about"
    const val ANSWER = "answer"
    const val DETAILS = "details"
}

/** Notifications let the agent speak first; the step counter shows it how you move. */
val AGENT_PERMISSIONS = arrayOf(Manifest.permission.POST_NOTIFICATIONS, Manifest.permission.ACTIVITY_RECOGNITION)

class MainActivity : ComponentActivity() {
    private val air: AirViewModel by viewModels()

    override fun onRestart() {
        super.onRestart()
        air.refreshIfStale()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            DelhiAirTheme {
                val state by air.state.collectAsState()
                val navController = rememberSwipeDismissableNavController()
                val firstRun = rememberLauncherForActivityResult(
                    ActivityResultContracts.RequestMultiplePermissions(),
                ) {}
                LaunchedEffect(Unit) {
                    val habits = HabitStore(this@MainActivity)
                    if (habits.autoSuggestions && !habits.askedPermissions) {
                        habits.askedPermissions = true
                        firstRun.launch(AGENT_PERMISSIONS)
                    }
                }
                var selected by remember { mutableIntStateOf(0) }
                val open: (String) -> Unit = { route ->
                    selected = 0
                    navController.navigate(route) { launchSingleTop = true }
                }
                AppScaffold {
                    SwipeDismissableNavHost(navController = navController, startDestination = Routes.HOME) {
                        composable(Routes.HOME) {
                            HomeScreen(
                                state = state,
                                onRefresh = { air.refresh(force = true) },
                                onOpen = open,
                                onAsk = { text -> air.ask(text, open) },
                                onQuickAsk = { activity -> air.quickAsk(activity, open) },
                                onForYou = { air.openForYou(open) },
                                onNotForMe = air::notForMe,
                                onNotice = air::say,
                                onDismissMessage = air::clearMessage,
                            )
                        }
                        composable(Routes.WINDOW) {
                            WindowScreen(
                                state = state,
                                selected = selected,
                                onSelect = { selected = it },
                                onDetails = { navController.navigate(Routes.DETAILS) },
                                onRemind = air::remind,
                                onNotice = air::say,
                                onDismissMessage = air::clearMessage,
                            )
                        }
                        composable(Routes.DETAILS) { DetailsScreen(state, selected) }
                        composable(Routes.PLAN) {
                            PlanScreen(state.request, air::update) { navController.navigate(Routes.LIMITS) }
                        }
                        composable(Routes.LIMITS) { LimitsScreen(state.request, air::update) }
                        composable(Routes.PLACES) {
                            PlacesScreen(
                                selected = state.request.place,
                                onPick = {
                                    air.usePlace(it)
                                    navController.popBackStack()
                                },
                                onCoordinates = { latitude, longitude ->
                                    air.useCoordinates(latitude, longitude)
                                    navController.popBackStack()
                                },
                            )
                        }
                        composable(Routes.COMPARE_PICK) {
                            ComparePickScreen {
                                air.compare(it)
                                navController.navigate(Routes.COMPARE) {
                                    popUpTo(Routes.COMPARE_PICK) { inclusive = true }
                                }
                            }
                        }
                        composable(Routes.COMPARE) { CompareScreen(state) }
                        composable(Routes.ABOUT) {
                            AboutScreen(state, air.stationsConfigured, air.agentConfigured)
                        }
                        composable(Routes.ANSWER) { AnswerScreen(state.agentAnswer.orEmpty(), state.heard) }
                    }
                    if (state.asking) Thinking()
                }
            }
        }
    }
}
