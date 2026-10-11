package com.f1predictor.frontendjava.dto;

public class ChampionPredictionDto {
    private Integer predicted_position;
    private Integer driver_id;
    private String name;
    private String code;
    private Double historical_points;
    private Double average_finish;
    private Double form_score;
    private Integer dnf_count;
    private Double reliability_rate;
    private Double constructor_strength;
    private Double momentum;
    private Double predicted_score;
    private Double win_probability;
    private ScoreBreakdownDto score_breakdown;

    public Integer getPredicted_position() { return predicted_position; }
    public void setPredicted_position(Integer predicted_position) { this.predicted_position = predicted_position; }

    public Integer getDriver_id() { return driver_id; }
    public void setDriver_id(Integer driver_id) { this.driver_id = driver_id; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getCode() { return code; }
    public void setCode(String code) { this.code = code; }

    public Double getHistorical_points() { return historical_points; }
    public void setHistorical_points(Double historical_points) { this.historical_points = historical_points; }

    public Double getAverage_finish() { return average_finish; }
    public void setAverage_finish(Double average_finish) { this.average_finish = average_finish; }

    public Double getForm_score() { return form_score; }
    public void setForm_score(Double form_score) { this.form_score = form_score; }

    public Integer getDnf_count() { return dnf_count; }
    public void setDnf_count(Integer dnf_count) { this.dnf_count = dnf_count; }

    public Double getPredicted_score() { return predicted_score; }
    public void setPredicted_score(Double predicted_score) { this.predicted_score = predicted_score; }

    public Double getWin_probability() { return win_probability; }
    public void setWin_probability(Double win_probability) { this.win_probability = win_probability; }

    public Double getReliability_rate() { return reliability_rate; }
    public void setReliability_rate(Double reliability_rate) { this.reliability_rate = reliability_rate; }

    public Double getConstructor_strength() { return constructor_strength; }
    public void setConstructor_strength(Double constructor_strength) { this.constructor_strength = constructor_strength; }

    public Double getMomentum() { return momentum; }
    public void setMomentum(Double momentum) { this.momentum = momentum; }

    public ScoreBreakdownDto getScore_breakdown() { return score_breakdown; }
    public void setScore_breakdown(ScoreBreakdownDto score_breakdown) { this.score_breakdown = score_breakdown; }
}