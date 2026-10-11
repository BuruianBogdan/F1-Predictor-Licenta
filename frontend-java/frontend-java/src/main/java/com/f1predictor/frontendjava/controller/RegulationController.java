package com.f1predictor.frontendjava.controller;

import com.f1predictor.frontendjava.service.FlaskApiService;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

@Controller
@RequestMapping("/regulations")
public class RegulationController {

    private final FlaskApiService api;

    public RegulationController(FlaskApiService api) {
        this.api = api;
    }

    @GetMapping
    public String view(Model model) {
        model.addAttribute("regulations", api.getMap("/regulations"));
        return "regulations";
    }

    @PostMapping
    public String save(@RequestParam Map<String, String> params, Model model) {
        Map<String, Object> body = new HashMap<>();
        for (Map.Entry<String, String> e : params.entrySet()) {
            try {
                body.put(e.getKey(), Double.parseDouble(e.getValue()));
            } catch (NumberFormatException ignored) {
            }
        }
        Map<String, Object> resp = api.postMap("/regulations", body);
        model.addAttribute("regulations", resp);
        model.addAttribute("savedMessage", "Saved.");
        return "regulations";
    }

    @PostMapping("/reset")
    public String reset(Model model) {
        Map<String, Object> resp = api.postMap("/regulations/reset", Map.of());
        model.addAttribute("regulations", resp);
        model.addAttribute("savedMessage", "Reset to defaults.");
        return "regulations";
    }
}
