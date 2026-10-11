package com.f1predictor.frontendjava.controller;

import com.f1predictor.frontendjava.service.FlaskApiService;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@Controller
@RequestMapping("/history")
public class HistoryController {

    private final FlaskApiService api;

    public HistoryController(FlaskApiService api) {
        this.api = api;
    }

    @GetMapping
    public String view(Model model) {
        model.addAttribute("history", api.getList("/prediction-history"));
        return "history";
    }

    @PostMapping("/evaluate")
    public String evaluate(Model model) {
        Map<String, Object> resp = api.postMap("/prediction-history/evaluate", Map.of());
        model.addAttribute("evaluation", resp);
        model.addAttribute("history", api.getList("/prediction-history"));
        return "history";
    }
}
