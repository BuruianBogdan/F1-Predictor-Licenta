package com.f1predictor.frontendjava.controller;
import com.f1predictor.frontendjava.service.FlaskApiService;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;
import java.util.*;

@Controller
public class PredictionController {
    private final FlaskApiService api;
    public PredictionController(FlaskApiService api) {this.api=api;}
    private void populate(Model model,Integer season,Integer raceId) {
        var context=api.getMap("/season/context");
        int selected=season!=null?season:((Number)context.get("active_season")).intValue();
        var races=api.getList("/races").stream().filter(r->((Number)r.get("season_year")).intValue()==selected).sorted(Comparator.comparingInt(r->((Number)r.get("round")).intValue())).toList();
        var availability=api.getMap("/predict/availability?season="+selected);
        races=races.stream().map(r->{
            Map<String,Object> enriched=new HashMap<>(r);
            Object state=availability.get(String.valueOf(r.get("race_id")));
            enriched.put("refresh_available",state instanceof Map<?,?> refreshState && Boolean.TRUE.equals(refreshState.get("live_refresh_available")));
            enriched.put("sprint_available",state instanceof Map<?,?> sprintState && Boolean.TRUE.equals(sprintState.get("sprint_available")));
            enriched.put("qualifying_available",state instanceof Map<?,?> value && Boolean.TRUE.equals(value.get("post_qualifying_available")));
            return enriched;
        }).toList();
        Object next=context.get("next_race");
        if(raceId==null && next instanceof Map<?,?> race && ((Number)race.get("season_year")).intValue()==selected) raceId=((Number)race.get("race_id")).intValue();
        if(raceId==null && !races.isEmpty())raceId=((Number)races.get(0).get("race_id")).intValue();
        model.addAttribute("context",context);model.addAttribute("selectedSeason",selected);model.addAttribute("races",races);model.addAttribute("raceId",raceId);
        model.addAttribute("drivers",api.getList("/drivers"));
        model.addAttribute("flaskBaseUrl",api.baseUrl());
        if(raceId!=null){
            var weekend=api.getMap("/weekend/"+raceId);
            if(weekend!=null&&!weekend.isEmpty())model.addAttribute("weekend",weekend);
        }
        final Integer chosen=raceId;
        model.addAttribute("qualifyingAvailable",races.stream().anyMatch(r->Objects.equals(r.get("race_id"),chosen)&&Boolean.TRUE.equals(r.get("qualifying_available"))));
    }
    @GetMapping("/predictions") public String view(@RequestParam(required=false) Integer season,@RequestParam(required=false) Integer raceId,
        @RequestParam(required=false) String mode,@RequestParam(defaultValue="RACE") String target,@RequestParam(required=false) String job,Model model){
        populate(model,season,raceId);
        if(mode==null){var state=model.asMap().get("weekend");mode=state instanceof Map<?,?> value && Boolean.TRUE.equals(value.get("refresh_allowed")) ? "LIVE" : "PRE_WEEKEND";}
        model.addAttribute("mode",mode);model.addAttribute("target",target);model.addAttribute("jobId",job);
        if("LIVE".equals(mode)) {
            var weekend=model.asMap().get("weekend");
            if(weekend instanceof Map<?,?> value && value.get("forecasts") instanceof Map<?,?> forecasts && forecasts.get("SPRINT".equals(target)?"sprint":"race") instanceof Map<?,?> prediction)model.addAttribute("prediction",prediction);
            else if(job==null) {
                try {model.addAttribute("prediction",api.getMap("/predict/live/"+model.asMap().get("raceId")+"?target="+target));}
                catch(FlaskApiService.ApiException e){if(e.getStatus()!=400)throw e;model.addAttribute("predictionError",e.getMessage());}
            }
        }
        return "predictions";
    }
    @PostMapping("/predictions/refresh") public String refresh(@RequestParam Integer raceId,@RequestParam(required=false) Integer season,@RequestParam(defaultValue="RACE") String target,Model model){
        try {
            var job=api.postMap("/weekend/"+raceId+"/refresh",Map.of());
            return "redirect:/predictions?raceId="+raceId+(season==null?"":"&season="+season)+"&mode=LIVE&target="+target+"&job="+job.get("id");
        } catch(FlaskApiService.ApiException e) {
            if(e.getStatus()!=400)throw e;
            populate(model,season,raceId);model.addAttribute("mode","LIVE");model.addAttribute("target",target);model.addAttribute("predictionError",e.getMessage());return "predictions";
        }
    }
    @PostMapping("/predictions") public String run(@RequestParam Integer raceId,@RequestParam(required=false) Integer season,@RequestParam(defaultValue="PRE_WEEKEND") String mode,
        @RequestParam(defaultValue="RACE") String target,@RequestParam(defaultValue="false") boolean market,@RequestParam(required=false) List<Integer> oddsDriverId,@RequestParam(required=false) List<Double> oddsValue,@RequestParam(required=false) String capturedAt,Model model){
        populate(model,season,raceId);List<Map<String,Object>> odds=new ArrayList<>();
        if(oddsDriverId!=null && oddsValue!=null)for(int i=0;i<Math.min(oddsDriverId.size(),oddsValue.size());i++)if(oddsDriverId.get(i)!=null && oddsValue.get(i)!=null)odds.add(Map.of("driver_id",oddsDriverId.get(i),"odds",oddsValue.get(i)));
        model.addAttribute("target",target);model.addAttribute("mode",mode);model.addAttribute("market",market);
        model.addAttribute("submittedOdds",odds);model.addAttribute("capturedAt",capturedAt);
        try {
            Map<String,Object> response;
            if("SPRINT".equals(target)) {
                if(market)throw new FlaskApiService.ApiException("Manual Grand Prix odds cannot be applied to the sprint market.",400,"INVALID_INPUT");
                response=api.getMap("/predict/sprint/"+raceId+"?mode="+mode);
            } else if(market){var body=new HashMap<String,Object>();body.put("mode",mode);body.put("odds",odds);if(capturedAt!=null&&!capturedAt.isBlank())body.put("captured_at",capturedAt);response=api.postMap("/predict/race/"+raceId+"/market",body);}
            else response=api.getMap("/predict/race/"+raceId+"?mode="+mode);
            model.addAttribute("prediction",response);
        } catch(FlaskApiService.ApiException exception) {
            if(exception.getStatus()!=400 && exception.getStatus()!=422)throw exception;
            model.addAttribute("predictionError",exception.getMessage());
            model.addAttribute("predictionErrorCode",exception.getCode());
            if("QUALIFYING_UNAVAILABLE".equals(exception.getCode())) {
                model.addAttribute("mode","PRE_WEEKEND");
                model.addAttribute("qualifyingAvailable",false);
            }
        }
        return "predictions";
    }
}
