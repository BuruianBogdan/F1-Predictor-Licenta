package com.f1predictor.frontendjava.controller;

import com.f1predictor.frontendjava.service.FlaskApiService;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

@Controller
@RequestMapping("/simulator")
public class SimulatorController {

    private final FlaskApiService api;

    public SimulatorController(FlaskApiService api) {
        this.api = api;
    }

    @GetMapping
    public String view(Model model,
                       @RequestParam(required = false) String runId,
                       @RequestParam(required = false) Map<String, Object> ignore) {
        model.addAttribute("scenarios", api.getList("/scenarios"));
        if (runId != null && !runId.isBlank()) {
            model.addAttribute("runResult", api.postMap("/scenarios/" + runId + "/run", Map.of()));
        }
        return "simulator";
    }

    @PostMapping("/create")
    public String create(@RequestParam Map<String, String> params, Model model) {
        Map<String, Object> body = new HashMap<>();
        body.put("name", params.getOrDefault("name", "Scenario"));
        body.put("description", params.getOrDefault("description", ""));
        body.put("notes", params.getOrDefault("notes", ""));
        body.put("grid_position", parseIntOrNull(params.get("grid_position")));
        body.put("wet_race", params.containsKey("wet_race"));
        body.put("target_race_id", parseIntOrNull(params.get("target_race_id")));
        body.put("driver_id", parseIntOrNull(params.get("driver_id")));
        body.put("constructor_id", parseIntOrNull(params.get("constructor_id")));
        body.put("pace_delta", parseDoubleOrZero(params.get("pace_delta")));
        body.put("reliability_delta", parseDoubleOrZero(params.get("reliability_delta")));
        body.put("dnf_risk_delta", parseDoubleOrZero(params.get("dnf_risk_delta")));
        api.postMap("/scenarios", body);
        return "redirect:/simulator";
    }

    @PostMapping("/run/{id}")
    public String run(@org.springframework.web.bind.annotation.PathVariable String id) {
        return "redirect:/simulator?runId=" + id;
    }

    @PostMapping("/delete/{id}")
    public String delete(@org.springframework.web.bind.annotation.PathVariable String id) {
        api.delete("/scenarios/" + id);
        return "redirect:/simulator";
    }

    private Integer parseIntOrNull(String s) {
        try { return (s == null || s.isBlank()) ? null : Integer.parseInt(s.trim()); }
        catch (Exception e) { return null; }
    }
    private Double parseDoubleOrZero(String s) {
        try { return (s == null || s.isBlank()) ? 0.0 : Double.parseDouble(s.trim()); }
        catch (Exception e) { return 0.0; }
    }
}
