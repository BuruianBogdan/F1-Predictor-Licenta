package com.f1predictor.frontendjava.dto;

import java.util.List;

public class RacePredictionResponseDto {
    private Integer race_id;
    private String race_name;
    private Integer season_year;
    private Integer round;
    private Boolean market_factor_used;
    private String message;
    private List<RacePredictionDto> predictions;

    public Integer getRace_id() { return race_id; }
    public void setRace_id(Integer race_id) { this.race_id = race_id; }

    public String getRace_name() { return race_name; }
    public void setRace_name(String race_name) { this.race_name = race_name; }

    public Integer getSeason_year() { return season_year; }
    public void setSeason_year(Integer season_year) { this.season_year = season_year; }

    public Integer getRound() { return round; }
    public void setRound(Integer round) { this.round = round; }

    public Boolean getMarket_factor_used() { return market_factor_used; }
    public void setMarket_factor_used(Boolean market_factor_used) { this.market_factor_used = market_factor_used; }

    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }

    public List<RacePredictionDto> getPredictions() { return predictions; }
    public void setPredictions(List<RacePredictionDto> predictions) { this.predictions = predictions; }
}