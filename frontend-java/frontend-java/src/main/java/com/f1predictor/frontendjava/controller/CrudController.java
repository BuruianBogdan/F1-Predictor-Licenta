package com.f1predictor.frontendjava.controller;

import com.f1predictor.frontendjava.service.FlaskApiService;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;

@Controller
public class CrudController {

    private final FlaskApiService api;

    public CrudController(FlaskApiService api) {
        this.api = api;
    }

    @GetMapping("/drivers")
    public String drivers(Model model) {
        var list = api.getList("/drivers");
        list.forEach(d -> d.put("fullName",
                String.valueOf(d.getOrDefault("forename", "")) + " " + d.getOrDefault("surname", "")));
        model.addAttribute("drivers", list);
        model.addAttribute("grid",api.getMap("/drivers/grid"));
        return "drivers";
    }

    @GetMapping("/constructors")
    public String constructors(Model model) {
        model.addAttribute("constructors", api.getList("/constructors"));
        return "constructors";
    }

    @GetMapping("/circuits")
    public String circuits(Model model) {
        model.addAttribute("circuits", api.getList("/circuits"));
        return "circuits";
    }

    @GetMapping("/races")
    public String races(@RequestParam(required=false) Integer season, Model model) {
        model.addAttribute("calendar", api.getMap("/calendar"+(season==null?"":"?season="+season)));
        return "races";
    }

    @GetMapping("/results")
    public String results(Model model) {
        model.addAttribute("results", api.getList("/results"));
        return "results";
    }

    @GetMapping("/standings")
    public String standings(@RequestParam(required=false) Integer season, Model model) {
        var context = api.getMap("/season/context");
        int selected = season != null ? season : ((Number)context.get("active_season")).intValue();
        model.addAttribute("context", context);model.addAttribute("selectedSeason",selected);
        model.addAttribute("driverStandings", api.getList("/standings/drivers?season="+selected));
        model.addAttribute("constructorStandings", api.getList("/standings/constructors?season="+selected));
        return "standings";
    }
}
