package com.f1predictor.frontendjava;

import com.f1predictor.frontendjava.service.FlaskApiService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.servlet.MockMvc;
import java.util.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import static org.hamcrest.Matchers.containsString;

@SpringBootTest
@AutoConfigureMockMvc
class FrontendRenderingTests {
    @Autowired MockMvc mvc;
    @MockBean FlaskApiService api;
    Map<String,Object> race,winner,overview,detail,context;
    static Map<String,Object> map(Object... pairs){var out=new LinkedHashMap<String,Object>();for(int i=0;i<pairs.length;i+=2)out.put((String)pairs[i],pairs[i+1]);return out;}
    @BeforeEach void setup(){
        race=map("race_id",999,"season_year",2031,"round",6,"race_name","Future Test Grand Prix","date","2031-07-13","race_status","COMPLETED");
        winner=map("driver_id",777,"driver_name","Arbitrary Test Winner","driver_number",77,"driver_code","ATW","driver_image","/images/driver-silhouette.svg","team_color","#abcdef","constructor_name","Independent Test Team","position",1,"grid",5,"points",25,"laps",60,"race_time","1:30:00","fastest_lap","1:20.0","status","Finished");
        context=map("active_season",2031,"seasons",List.of(2030,2031),"next_race",race);
        overview=map("active_season",2031,"stale",false,"winner",winner,"latest_completed_race",race,"next_race",race,"prediction_preview",null,"model_metrics",Map.of(),"top_drivers",List.of(),"latest_podium",List.of(winner),"market",null,"last_sync_at","2031-07-14T00:00:00Z","stats",map("drivers",22,"constructors",11,"races",6,"results",132));
        detail=map("race",race,"circuit",map("name","Test Circuit","location","Local","country","Test"),"winner",winner,"podium",List.of(winner),"results",List.of(winner),"weather",List.of(),"prediction_review",null,"prediction_review_note","No genuine pre-race prediction was recorded");
        when(api.getMap("/dashboard/overview")).thenReturn(overview);when(api.getMap("/season/context")).thenReturn(context);
        when(api.getMap("/races/999/detail")).thenReturn(detail);when(api.getList("/races")).thenReturn(List.of(race));when(api.getList("/drivers")).thenReturn(List.of());
        when(api.getMap("/predict/availability?season=2031")).thenReturn(map("999",map("post_qualifying_available",false)));
    }
    @Test void dashboardRendersAnyWinnerAndDynamicSeason() throws Exception{
        mvc.perform(get("/")).andExpect(status().isOk()).andExpect(content().string(containsString("Arbitrary Test Winner"))).andExpect(content().string(containsString("2031")));
        verify(api,never()).getList("/predict/champion");
    }
    @Test void predictionsRendersWithoutHardcodedRaceOne() throws Exception{
        mvc.perform(get("/predictions")).andExpect(status().isOk()).andExpect(content().string(containsString("Future Test Grand Prix")));
    }
    @Test void raceDetailRendersArbitraryWinner() throws Exception{
        mvc.perform(get("/races/999")).andExpect(status().isOk()).andExpect(content().string(containsString("Independent Test Team")));
    }
    @Test void noWinnerAndUpcomingRaceRenderWithoutNullErrors() throws Exception{
        overview.put("winner",null);overview.put("latest_completed_race",null);detail.put("winner",null);detail.put("podium",List.of());detail.put("results",List.of());
        mvc.perform(get("/")).andExpect(status().isOk());mvc.perform(get("/races/999")).andExpect(status().isOk());
    }
    @Test void apiFailureIsFriendly() throws Exception{
        when(api.getMap("/dashboard/overview")).thenThrow(new FlaskApiService.ApiException("The data service is unavailable."));
        mvc.perform(get("/")).andExpect(status().isServiceUnavailable()).andExpect(content().string(containsString("The data service is unavailable.")));
    }
    @Test void unavailableQualifyingKeepsTheFormAndOffersPreWeekend() throws Exception {
        when(api.getMap("/predict/race/999?mode=POST_QUALIFYING")).thenThrow(new FlaskApiService.ApiException("Qualifying results are not available yet.",400,"QUALIFYING_UNAVAILABLE"));
        mvc.perform(post("/predictions").param("raceId","999").param("season","2031").param("mode","POST_QUALIFYING"))
            .andExpect(status().isOk()).andExpect(view().name("predictions"))
            .andExpect(model().attribute("mode","PRE_WEEKEND"))
            .andExpect(content().string(containsString("Pre-weekend is selected")))
            .andExpect(xpath("//select[@id='mode']/option[@value='POST_QUALIFYING']/@disabled").exists())
            .andExpect(xpath("//form[@action='/predictions' and @method='post']").exists());
        verify(api,never()).getMap("/predict/race/999?mode=PRE_WEEKEND");
    }
    @Test void knownQualifyingEnablesTheMode() throws Exception {
        when(api.getMap("/predict/availability?season=2031")).thenReturn(map("999",map("post_qualifying_available",true)));
        mvc.perform(get("/predictions")).andExpect(status().isOk())
            .andExpect(xpath("//select[@id='mode']/option[@value='POST_QUALIFYING']/@disabled").doesNotExist());
    }
    @Test void marketValidationPreservesSubmittedOddsAndTimestamp() throws Exception {
        when(api.getList("/drivers")).thenReturn(List.of(map("driver_id",777,"forename","Test","surname","Pilot")));
        when(api.postMap(eq("/predict/race/999/market"),any())).thenThrow(new FlaskApiService.ApiException("Odds were captured after the cutoff.",400,"INVALID_INPUT"));
        mvc.perform(post("/predictions").param("raceId","999").param("season","2031").param("market","true").param("oddsDriverId","777").param("oddsValue","3.5").param("capturedAt","2031-07-14T00:00:00Z"))
            .andExpect(status().isOk()).andExpect(view().name("predictions"))
            .andExpect(content().string(containsString("Odds were captured after the cutoff.")))
            .andExpect(xpath("//input[@name='oddsValue']/@value").string("3.5"))
            .andExpect(xpath("//input[@name='capturedAt']/@value").string("2031-07-14T00:00:00Z"))
            .andExpect(xpath("//select[@name='oddsDriverId']/option[@value='777']/@selected").exists())
            .andExpect(xpath("//input[@name='market']/@checked").exists());
    }
    @Test void predictionOutageStillUsesServiceErrorPage() throws Exception {
        when(api.getMap("/predict/race/999?mode=PRE_WEEKEND")).thenThrow(new FlaskApiService.ApiException("The data service is unavailable."));
        mvc.perform(post("/predictions").param("raceId","999")).andExpect(status().isServiceUnavailable()).andExpect(view().name("service-error"));
    }

    @Test void calendarRendersOrderedGroupsAndCircuitPaths() throws Exception {
        var circuit=map("name","Test Circuit","country","Testland","layout_available",true,"path","M10,20 L30,40","start_x",10,"start_y",20,"length_km",5.1);
        var upcoming=new HashMap<>(race);upcoming.put("circuit",circuit);upcoming.put("sprint_at",null);
        when(api.getMap("/calendar")).thenReturn(map("context",context,"season",2031,"next",upcoming,"remaining_count",1,"completed_count",0,"upcoming",List.of(upcoming),"completed",List.of(),"pending",List.of(),"other",List.of()));
        mvc.perform(get("/races")).andExpect(status().isOk()).andExpect(content().string(containsString("Next on the calendar"))).andExpect(content().string(containsString("M10,20 L30,40")));
    }
    @Test void newsEmptyAndPendingStatesRemainUsable() throws Exception {
        var state=map("enabled",true,"article_count",0,"llm",map("available",false),"runs",List.of(),"pending_summaries",0,"next_run_at",null,"source_url","https://www.formula1.com/en/latest");
        when(api.getMap("/news")).thenReturn(map("status",state,"articles",List.of()));
        mvc.perform(get("/news")).andExpect(status().isOk()).andExpect(content().string(containsString("The first edition is on its way")));
        var article=map("source_url","https://www.formula1.com/en/latest/article/test","source_title","Source title","title","Source title","summary_status","pending","published_at","2031-07-13T10:00:00Z","image_url",null,"signals",List.of());
        when(api.getMap("/news")).thenReturn(map("status",state,"articles",List.of(article)));
        mvc.perform(get("/news")).andExpect(status().isOk()).andExpect(content().string(containsString("Local summary pending")));
    }
    @Test void newsRefreshRedirectsToBackgroundOperation() throws Exception {
        when(api.postMap(eq("/news/refresh"),any())).thenReturn(map("id","abc123"));
        mvc.perform(post("/news/refresh")).andExpect(status().is3xxRedirection()).andExpect(redirectedUrl("/news?job=abc123"));
    }
    @Test void winnerIncludesCircuitBetweenCopyAndPortrait() throws Exception {
        race.put("circuit",map("name","Test Circuit","location","Local","country","Test","layout_available",true,"path","M10,20 L30,40","start_x",10,"start_y",20,"length_km",5.1));
        mvc.perform(get("/")).andExpect(status().isOk()).andExpect(xpath("//div[@class='hero-copy']/following-sibling::div[1][@class='hero-circuit']").exists()).andExpect(xpath("//div[@class='hero-circuit']/following-sibling::div[1][@class='hero-visual']").exists());
    }

    @Test void weekendRefreshQueuesAndPreservesSprintSelection() throws Exception {
        when(api.postMap(eq("/weekend/999/refresh"),any())).thenReturn(map("id","abc123"));
        mvc.perform(post("/predictions/refresh").param("raceId","999").param("season","2031").param("target","SPRINT"))
            .andExpect(status().is3xxRedirection()).andExpect(redirectedUrl("/predictions?raceId=999&season=2031&mode=LIVE&target=SPRINT&job=abc123"));
    }
    @Test void liveSessionCardsAndSprintForecastRender() throws Exception {
        var row=map("driver_name","Test Pilot","position",1,"time_text","1:32.274","laps",20,"points",null);
        var session=map("code","FP1","name","Practice 1","status","available","leader",row,"rows",List.of(row),"observed_at","2031-07-10T10:00:00Z","source_url","https://www.formula1.com","start_at","2031-07-10T09:00:00Z");
        var p=map("driver_id",777,"driver_name","Test Pilot","driver_code","TST","constructor_name","Test Team","team_color","#abcdef","driver_image","/images/driver-silhouette.svg","predicted_position",1,"win_probability",.2,"model_probability",.1,"session_probability",.2,"news_adjusted_probability",.2,"final_probability",.2,"market_probability",null,"podium_probability",.5,"points_probability",.8,"expected_points",4.2,"factors",Map.of(),"session_evidence",List.of(),"news_signals",List.of());
        var forecast=map("predictions",List.of(p),"target","SPRINT","mode","LIVE","race_name","Future Test Grand Prix","historical_replay",false,"news_factor_used",false,"market_factor_used",false,"session_factor_used",true,"live_method","Session mixture","limitations",List.of("Experimental"),"points_places",8,"model_version","test-weekend","feature_cutoff","2031-07-10T10:00:00Z","training_cutoff","2030-12-31T00:00:00Z");
        when(api.getMap("/weekend/999")).thenReturn(map("refresh_allowed",true,"status","SUCCESS","last_success_at","2031-07-10T10:00:00Z","sessions",List.of(session),"forecasts",map("sprint",forecast)));
        mvc.perform(get("/predictions").param("raceId","999").param("mode","LIVE").param("target","SPRINT"))
            .andExpect(status().isOk()).andExpect(content().string(containsString("Update weekend")))
            .andExpect(content().string(containsString("1:32.274"))).andExpect(content().string(containsString("Points finish · top 8")))
            .andExpect(content().string(containsString("Expected points")));
    }
    @Test void sprintRejectsGrandPrixMarketOddsWithoutAnOutagePage() throws Exception {
        mvc.perform(post("/predictions").param("raceId","999").param("target","SPRINT").param("mode","LIVE").param("market","true"))
            .andExpect(status().isOk()).andExpect(content().string(containsString("Grand Prix odds cannot be applied to the sprint")));
    }
    @Test void liveRefreshValidationKeepsTheUpdatePage() throws Exception {
        when(api.postMap(eq("/weekend/999/refresh"),any())).thenThrow(new FlaskApiService.ApiException("A refresh is already running",400,"INVALID_INPUT"));
        mvc.perform(post("/predictions/refresh").param("raceId","999"))
            .andExpect(status().isOk()).andExpect(view().name("predictions")).andExpect(content().string(containsString("A refresh is already running")));
    }

    @Test void championshipDisplaysSimulationSavedByWeekendRefresh() throws Exception {
        var simulation=map("simulations",5000,"remaining_races",7,"remaining_sprints",1,"drivers",List.of(),"news_factor_used",false,"weekend_adjusted_races",List.of(999),"limitations",List.of("Experimental"));
        when(api.getMap("/weekend/999")).thenReturn(map("forecasts",map("championship",simulation)));
        mvc.perform(get("/championship")).andExpect(status().isOk()).andExpect(model().attribute("simulation",simulation))
            .andExpect(content().string(containsString("5000 SIMULATIONS"))).andExpect(content().string(containsString("Updated with published weekend evidence")));
    }

    @Test void raceControlRendersStandaloneWithoutNavbar() throws Exception {
        mvc.perform(get("/race-control/999").param("standalone","true")).andExpect(status().isOk())
            .andExpect(xpath("//nav[@class='navbar']").doesNotExist())
            .andExpect(xpath("//main[@data-race-id='999']").exists())
            .andExpect(content().string(containsString("Timing tower")))
            .andExpect(content().string(containsString("favorite-driver")));
    }
    @Test void diagnosticsAndProjectionStayInExistingViewer() throws Exception {
        mvc.perform(get("/race-control/999").param("standalone","true")).andExpect(status().isOk())
            .andExpect(xpath("//dialog[@id='feed-diagnostics']").exists())
            .andExpect(xpath("//tbody[@id='projection-rows']").exists())
            .andExpect(xpath("//b[@id='car-rpm']").exists());
        mvc.perform(get("/screen-timing")).andExpect(status().isNotFound());
        mvc.perform(get("/live-timing")).andExpect(status().isNotFound());
    }
    @Test void diagnosticsProxyPreservesSessionAndCutoff() throws Exception {
        when(api.getMap("/race-control/999/700/diagnostics?mode=LIVE&at=100.0")).thenReturn(map("state","STALE","session_key",700));
        mvc.perform(get("/race-control/api/999/700/diagnostics").param("mode","LIVE").param("at","100"))
            .andExpect(status().isOk()).andExpect(jsonPath("$.state").value("STALE"));
        verify(api).getMap("/race-control/999/700/diagnostics?mode=LIVE&at=100.0");
    }
    @Test void championshipProxyRestrictsScoringAndKeepsUnknownEligibility() throws Exception {
        when(api.getMap("/race-control/999/700/championship-projection?mode=REPLAY&scoring=STOPPED_NOW&at=100.0")).thenReturn(map("status","UNVERIFIED_STOPPAGE_RULES"));
        mvc.perform(get("/race-control/api/999/700/championship-projection").param("at","100").param("scoring","STOPPED_NOW"))
            .andExpect(status().isOk()).andExpect(jsonPath("$.status").value("UNVERIFIED_STOPPAGE_RULES"));
    }
    @Test void crossOriginCannotStopSharedFeed() throws Exception {
        mvc.perform(post("/race-control/api/999/700/stop").header("Origin","https://unrelated.example"))
            .andExpect(status().isForbidden());
        verify(api,never()).postMap(eq("/race-control/999/700/stop"),any());
    }
    @Test void timingProxyKeepsFailuresAsJson() throws Exception {
        when(api.getMap("/race-control/999/catalog")).thenThrow(new FlaskApiService.ApiException("Timing unavailable",502,"PROVIDER_UNAVAILABLE"));
        mvc.perform(get("/race-control/api/999/catalog")).andExpect(status().isBadGateway())
            .andExpect(jsonPath("$.error.message").value("Timing unavailable"));
    }
    @Test void liveViewerChoosesActiveRace() throws Exception {
        context.put("awaiting_results",List.of(race));
        mvc.perform(get("/race-control")).andExpect(redirectedUrl("/race-control/999"));
    }

    @Test void raceControlIncludesTyreEstimateIncidentAndStrategyPanels() throws Exception {
        mvc.perform(get("/race-control/999")).andExpect(status().isOk())
            .andExpect(content().string(containsString("One estimated index for the tyre set")))
            .andExpect(xpath("//svg[@id='health-car']").exists())
            .andExpect(xpath("//ol[@id='outlook-rows']").exists())
            .andExpect(xpath("//g[@id='car-labels']").exists())
            .andExpect(content().string(containsString("Incident feed")));
    }
    @Test void timingProxyBoundsTheLookaheadWindowForFastReplay() throws Exception {
        when(api.getMap("/race-control/999/100/frame?mode=REPLAY&at=42.0&driver=63&scoring=FULL_DISTANCE&window=240")).thenReturn(Map.of("phase","BREAK"));
        mvc.perform(get("/race-control/api/999/100/frame").param("at","42").param("driver","63").param("window","9999"))
            .andExpect(status().isOk()).andExpect(jsonPath("$.phase").value("BREAK"));
    }
    @Test void removedPagesReturnNotFoundAndToolsKeepsRefresh() throws Exception {
        mvc.perform(get("/live-timing")).andExpect(status().isNotFound());
        mvc.perform(get("/screen-timing")).andExpect(status().isNotFound());
        mvc.perform(get("/")).andExpect(status().isOk())
            .andExpect(xpath("//button[@data-refresh-sessions]").exists())
            .andExpect(xpath("//a[@href='/live-timing' or @href='/screen-timing']").doesNotExist());
    }
    @Test void sessionRefreshProxyPreservesErrors() throws Exception {
        when(api.getMap("/race-control/sessions/refresh")).thenThrow(new FlaskApiService.ApiException("No updates",400,"INVALID_INPUT"));
        mvc.perform(get("/race-control/api/sessions/refresh")).andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.error.message").value("No updates"));
    }
    @Test void sessionRefreshQueuesThroughOriginalRaceControlService() throws Exception {
        when(api.postMap(eq("/race-control/sessions/refresh"),any())).thenReturn(map("id","one","status","QUEUED"));
        mvc.perform(post("/race-control/api/sessions/refresh").contentType("application/json").content("{}"))
            .andExpect(status().isAccepted()).andExpect(jsonPath("$.id").value("one"));
    }
    @Test void sessionRefreshRejectsRemoteAndCrossOriginCalls() throws Exception {
        mvc.perform(post("/race-control/api/sessions/refresh").with(r->{r.setRemoteAddr("10.0.0.8");return r;})
            .contentType("application/json").content("{}"))
            .andExpect(status().isForbidden());
        mvc.perform(post("/race-control/api/sessions/refresh").header("Origin","https://untrusted.example")
            .contentType("application/json").content("{}"))
            .andExpect(status().isForbidden());
    }
}
