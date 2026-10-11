package com.f1predictor.frontendjava.controller;
import com.f1predictor.frontendjava.service.FlaskApiService;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.*;
import java.util.function.Supplier;

@Controller
public class RaceControlController {
    private final FlaskApiService api;
    public RaceControlController(FlaskApiService api){this.api=api;}
    @GetMapping("/race-control") public String current(){
        var context=api.getMap("/season/context");
        Object race=context.get("next_race");
        if(context.get("awaiting_results") instanceof List<?> pending && !pending.isEmpty())race=pending.get(0);
        if(!(race instanceof Map<?,?>))race=context.get("latest_completed_race");
        return race instanceof Map<?,?> event ? "redirect:/race-control/"+event.get("race_id") : "redirect:/races";
    }
    @GetMapping("/race-control/{id}") public String viewer(@PathVariable int id,@RequestParam(defaultValue="false") boolean standalone,Model model){
        model.addAttribute("raceId",id);model.addAttribute("standalone",standalone);return "race-control";
    }
    private ResponseEntity<Map<String,Object>> json(Supplier<Map<String,Object>> operation){
        try{return ResponseEntity.ok(operation.get());}
        catch(FlaskApiService.ApiException e){return ResponseEntity.status(e.getStatus()).body(Map.of("error",Map.of("message",e.getMessage(),"code",e.getCode())));}
    }
    @GetMapping("/race-control/api/{id}/catalog") @ResponseBody public ResponseEntity<Map<String,Object>> catalog(@PathVariable int id){return json(()->api.getMap("/race-control/"+id+"/catalog"));}
    @PostMapping("/race-control/api/{id}/catalog") @ResponseBody public ResponseEntity<Map<String,Object>> refresh(@PathVariable int id){return json(()->api.postMap("/race-control/"+id+"/catalog",Map.of()));}
    @PostMapping("/race-control/api/{id}/{key}/prepare") @ResponseBody public ResponseEntity<Map<String,Object>> prepare(@PathVariable int id,@PathVariable int key,@RequestBody Map<String,Object> body){return json(()->api.postMap("/race-control/"+id+"/"+key+"/prepare",Map.of("mode",mode(String.valueOf(body.getOrDefault("mode","REPLAY"))))));}
    @GetMapping("/race-control/api/{id}/{key}/status") @ResponseBody public ResponseEntity<Map<String,Object>> status(@PathVariable int id,@PathVariable int key,@RequestParam(defaultValue="REPLAY") String mode){return json(()->api.getMap("/race-control/"+id+"/"+key+"/status?mode="+mode(mode)));}
    @GetMapping("/race-control/api/{id}/{key}/frame") @ResponseBody public ResponseEntity<Map<String,Object>> frame(@PathVariable int id,@PathVariable int key,@RequestParam(defaultValue="REPLAY") String mode,@RequestParam(required=false) Double at,@RequestParam(required=false) Integer driver,@RequestParam(defaultValue="30") int window){
        return json(()->api.getMap("/race-control/"+id+"/"+key+"/frame?mode="+mode(mode)+(at!=null && Double.isFinite(at)?"&at="+at:"")+(driver!=null?"&driver="+driver:"")+"&window="+Math.max(20,Math.min(240,window))));
    }
    private String mode(String value){return "LIVE".equalsIgnoreCase(value)?"LIVE":"REPLAY";}
}
