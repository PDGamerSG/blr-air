package com.delhiair.watch.ui

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.wear.compose.material3.AppScaffold
import androidx.wear.compose.navigation.SwipeDismissableNavHost
import androidx.wear.compose.navigation.composable
import androidx.wear.compose.navigation.rememberSwipeDismissableNavController

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
}

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
                val viewModel: AirViewModel = viewModel()
                val state by viewModel.state.collectAsState()
                val navController = rememberSwipeDismissableNavController()
                AppScaffold {
                    SwipeDismissableNavHost(navController = navController, startDestination = Routes.HOME) {
                        composable(Routes.HOME) {
                            HomeScreen(
                                state = state,
                                onRefresh = { viewModel.refresh(force = true) },
                                onOpen = { navController.navigate(it) },
                                onAsk = { text -> viewModel.ask(text) { navController.navigate(it) } },
                                onNotice = viewModel::say,
                                onDismissMessage = viewModel::clearMessage,
                            )
                        }
                        composable(Routes.WINDOW) {
                            WindowScreen(
                                state = state,
                                onRemind = viewModel::remind,
                                onNotice = viewModel::say,
                                onDismissMessage = viewModel::clearMessage,
                            )
                        }
                        composable(Routes.PLAN) {
                            PlanScreen(state.request, viewModel::update) { navController.navigate(Routes.LIMITS) }
                        }
                        composable(Routes.LIMITS) {
                            LimitsScreen(state.request, viewModel::update)
                        }
                        composable(Routes.PLACES) {
                            PlacesScreen(
                                selected = state.request.place,
                                onPick = {
                                    viewModel.usePlace(it)
                                    navController.popBackStack()
                                },
                                onCoordinates = { latitude, longitude ->
                                    viewModel.useCoordinates(latitude, longitude)
                                    navController.popBackStack()
                                },
                            )
                        }
                        composable(Routes.COMPARE_PICK) {
                            ComparePickScreen {
                                viewModel.compare(it)
                                navController.navigate(Routes.COMPARE) {
                                    popUpTo(Routes.COMPARE_PICK) { inclusive = true }
                                }
                            }
                        }
                        composable(Routes.COMPARE) {
                            CompareScreen(state)
                        }
                        composable(Routes.ABOUT) {
                            AboutScreen(state, viewModel.stationsConfigured, viewModel.agentConfigured)
                        }
                        composable(Routes.ANSWER) {
                            AnswerScreen(state.agentAnswer.orEmpty())
                        }
                    }
                }
            }
        }
    }
}
