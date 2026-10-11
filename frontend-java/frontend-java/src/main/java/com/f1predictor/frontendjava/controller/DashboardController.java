package com.f1predictor.frontendjava.controller;
import com.f1predictor.frontendjava.service.FlaskApiService;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
@Controller
public class DashboardController {
    private final FlaskApiService api;
    public DashboardController(FlaskApiService api) { this.api=api; }
    @GetMapping("/") public String index(Model model) {
        model.addAttribute("overview",api.getMap("/dashboard/overview"));return "index";
    }
}
