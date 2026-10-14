package com.f1predictor.frontendjava.controller;
import com.f1predictor.frontendjava.service.FlaskApiService;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.*;
import java.util.function.Supplier;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Value;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

@Controller
public class RaceControlController {
    private final FlaskApiService api;
    @Value("${flask.api.admin-token:}") private String adminToken;
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
    @GetMapping("/race-control/api/{id}/{key}/frame") @ResponseBody public ResponseEntity<Map<String,Object>> frame(@PathVariable int id,@PathVariable int key,@RequestParam(defaultValue="REPLAY") String mode,@RequestParam(required=false) Double at,@RequestParam(required=false) Integer driver,@RequestParam(defaultValue="30") int window,@RequestParam(defaultValue="FULL_DISTANCE") String scoring){
        return json(()->api.getMap("/race-control/"+id+"/"+key+"/frame?mode="+mode(mode)+(at!=null && Double.isFinite(at)?"&at="+at:"")+(driver!=null?"&driver="+driver:"")+"&scoring="+("STOPPED_NOW".equals(scoring)?"STOPPED_NOW":"FULL_DISTANCE")+"&window="+Math.max(20,Math.min(240,window))));
    }
    private String mode(String value){return "LIVE".equalsIgnoreCase(value)?"LIVE":"REPLAY";}
    @GetMapping("/race-control/api/providers") @ResponseBody public ResponseEntity<Map<String,Object>> providers(){return json(()->api.getMap("/race-control/providers"));}
    @GetMapping("/race-control/api/health") @ResponseBody public ResponseEntity<Map<String,Object>> health(){return json(()->api.getMap("/race-control/health"));}
    @GetMapping("/race-control/api/{id}/{key}/diagnostics") @ResponseBody public ResponseEntity<Map<String,Object>> diagnostics(@PathVariable int id,@PathVariable int key,@RequestParam(defaultValue="LIVE") String mode,@RequestParam(required=false) Double at){return json(()->api.getMap("/race-control/"+id+"/"+key+"/diagnostics?mode="+mode(mode)+(at!=null&&Double.isFinite(at)?"&at="+at:"")));}
    @GetMapping("/race-control/api/{id}/{key}/capabilities") @ResponseBody public ResponseEntity<Map<String,Object>> capabilities(@PathVariable int id,@PathVariable int key,@RequestParam(defaultValue="LIVE") String mode){return json(()->api.getMap("/race-control/"+id+"/"+key+"/capabilities?mode="+mode(mode)));}
    @GetMapping("/race-control/api/{id}/{key}/championship-projection") @ResponseBody public ResponseEntity<Map<String,Object>> championship(@PathVariable int id,@PathVariable int key,@RequestParam(defaultValue="REPLAY") String mode,@RequestParam(required=false) Double at,@RequestParam(defaultValue="FULL_DISTANCE") String scoring){return json(()->api.getMap("/race-control/"+id+"/"+key+"/championship-projection?mode="+mode(mode)+"&scoring="+("STOPPED_NOW".equals(scoring)?"STOPPED_NOW":"FULL_DISTANCE")+(at!=null&&Double.isFinite(at)?"&at="+at:"")));}
    @PostMapping("/race-control/api/{id}/{key}/stop") @ResponseBody public ResponseEntity<Map<String,Object>> stop(@PathVariable int id,@PathVariable int key,HttpServletRequest request){
        String origin=request.getHeader("Origin");
        boolean sameOrigin=origin==null||origin.equals("http://127.0.0.1:"+request.getServerPort())||origin.equals("http://localhost:"+request.getServerPort());
        boolean local=Set.of("127.0.0.1","::1","0:0:0:0:0:0:0:1").contains(request.getRemoteAddr());
        boolean token=adminToken!=null&&!adminToken.isBlank()&&MessageDigest.isEqual(("Bearer "+adminToken).getBytes(StandardCharsets.UTF_8),String.valueOf(request.getHeader("Authorization")).getBytes(StandardCharsets.UTF_8));
        if(!sameOrigin||!local&&!token)return ResponseEntity.status(403).body(Map.of("error",Map.of("message","Stopping a feed is local or token-authorized and same-origin only")));
        return json(()->api.postMap("/race-control/"+id+"/"+key+"/stop",Map.of()));
    }
}
