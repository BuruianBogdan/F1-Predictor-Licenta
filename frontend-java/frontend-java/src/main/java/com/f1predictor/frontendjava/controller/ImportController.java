package com.f1predictor.frontendjava.controller;

import com.f1predictor.frontendjava.service.FlaskApiService;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@Controller
public class ImportController {

    private final FlaskApiService api;

    public ImportController(FlaskApiService api) {
        this.api = api;
    }

    @GetMapping("/import")
    public String view(Model model) {
        return "redirect:/data";
    }

    @PostMapping("/import")
    public String doImport(@RequestParam(defaultValue = "2020") Integer startYear,
                           @RequestParam(required = false) Integer endYear,
                           Model model) {
        Map<String, Object> resp = api.postMap("/data/import",
                Map.of("start_year", startYear, "end_year", endYear != null ? endYear : java.time.Year.now().getValue()));
        model.addAttribute("importResponse", resp);
        return "redirect:/data";
    }

    @PostMapping("/import/refresh-live")
    public String refreshLive(Model model) {
        Map<String, Object> resp = api.postMap("/data/refresh-live", Map.of());
        model.addAttribute("importResponse", resp);
        return "redirect:/data";
    }
}
