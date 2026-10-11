package com.f1predictor.frontendjava.controller;
import com.f1predictor.frontendjava.service.FlaskApiService;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;
import java.util.*;

@Controller
public class IntelligenceController {
    private final FlaskApiService api;
    public IntelligenceController(FlaskApiService api){this.api=api;}
    @GetMapping("/races/{id}") public String race(@PathVariable int id,Model model){model.addAttribute("detail",api.getMap("/races/"+id+"/detail"));return "race-detail";}
    @PostMapping("/races/{id}/story") public String story(@PathVariable int id,@RequestParam(defaultValue="en") String lang,Model model){
        model.addAttribute("detail",api.getMap("/races/"+id+"/detail"));model.addAttribute("story",api.postMap("/explanations/race/"+id+"?lang="+lang,Map.of()));return "race-detail";
    }
    @GetMapping("/drivers/{id}") public String driver(@PathVariable int id,Model model){model.addAttribute("detail",api.getMap("/drivers/"+id+"/detail"));return "driver-detail";}
    @GetMapping("/model") public String model(Model model){model.addAttribute("metrics",api.getMap("/model/metrics"));return "model";}
    @GetMapping("/championship") public String championship(Model model){
        var context=api.getMap("/season/context");
        model.addAttribute("context",context);model.addAttribute("standings",api.getList("/standings/drivers"));
        if(context.get("next_race") instanceof Map<?,?> race){
            var weekend=api.getMap("/weekend/"+race.get("race_id"));
            if(weekend!=null && weekend.get("forecasts") instanceof Map<?,?> forecasts && forecasts.get("championship") instanceof Map<?,?> simulation)model.addAttribute("simulation",simulation);
        }
        return "championship";
    }
    @PostMapping("/championship") public String simulate(Model model){
        championship(model);model.addAttribute("simulation",api.getMap("/predict/championship"));return "championship";
    }
    @GetMapping("/data") public String data(@RequestParam(required=false) String job,Model model){
        model.addAttribute("overview",api.getMap("/dashboard/overview"));model.addAttribute("sync",api.getMap("/data/sync/status"));model.addAttribute("oddsStatus",api.getMap("/odds/status"));model.addAttribute("jobId",job);return "data";
    }
    @PostMapping("/data/action") public String action(@RequestParam String action,@RequestParam(required=false) Integer startYear,@RequestParam(required=false) Integer endYear,Model model){
        Map<String,Object> result;
        switch(action){
            case "sync": result=api.postMap("/data/sync/current?background=true",Map.of());break;
            case "history": result=api.postMap("/data/sync/history",Map.of("start_year",startYear==null?2014:startYear,"end_year",endYear==null?java.time.Year.now().getValue():endYear));break;
            case "train": result=api.postMap("/model/retrain",Map.of());break;
            case "odds": var context=api.getMap("/season/context");if(context.get("next_race") instanceof Map<?,?> race) result=api.postMap("/odds/refresh/"+race.get("race_id"),Map.of());else result=Map.of("message","No upcoming race");break;
            case "quality": result=api.getMap("/data/quality");break;
            default:throw new IllegalArgumentException("Unknown action");
        }
        if(result.containsKey("id"))return "redirect:/data?job="+result.get("id");
        data(null,model);model.addAttribute("operationResult",result);return "data";
    }
    @GetMapping("/data/jobs/{id}") @ResponseBody public Map<String,Object> job(@PathVariable String id){
        if(!id.matches("[a-f0-9]{32}"))return Map.of("status","FAILED","error","Invalid job ID");
        return api.getMap("/data/jobs/"+id);
    }
}
