package com.f1predictor.frontendjava.controller;
import com.f1predictor.frontendjava.service.FlaskApiService;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;
import java.util.Map;

@Controller
public class NewsController {
    private final FlaskApiService api;
    public NewsController(FlaskApiService api){this.api=api;}
    @GetMapping("/news") public String news(@RequestParam(required=false) String job,Model model){
        model.addAttribute("news",api.getMap("/news"));model.addAttribute("jobId",job);return "news";
    }
    @PostMapping("/news/refresh") public String refresh(){return "redirect:/news?job="+api.postMap("/news/refresh",Map.of()).get("id");}
    @PostMapping("/news/automation") public String automation(@RequestParam boolean enabled){
        api.postMap("/news/automation",Map.of("enabled",enabled,"interval_minutes",30));return "redirect:/news";
    }
}
