package com.f1predictor.frontendjava.controller;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;

@Controller
@RequestMapping("/export")
public class ExportController {

    @Value("${flask.api.base-url}")
    private String flaskBaseUrl;

    @GetMapping
    public String view(Model model) {
        model.addAttribute("flaskBaseUrl", flaskBaseUrl);
        return "export";
    }
}
