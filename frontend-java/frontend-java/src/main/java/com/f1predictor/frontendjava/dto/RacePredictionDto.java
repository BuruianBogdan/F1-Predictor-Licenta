package com.f1predictor.frontendjava.dto;

public class RacePredictionDto {
    private Integer predicted_position;
    private Integer predicted_position_with_market;
    private Integer driver_id;
    private String driver_name;
    private String driver_code;
    private Integer constructor_id;
    private String constructor_name;
    private Integer grid;
    private Integer position;
    private Double points;
    private String status;
    private Double form_score;
    private Double reliability_rate;
    private Double constructor_strength;
    private Double predicted_score;
    private Double win_probability;
    private Double market_probability;
    private Double final_probability;
    private ScoreBreakdownDto score_breakdown;

    public Integer getPredicted_position() { return predicted_position; }
    public void setPredicted_position(Integer predicted_position) { this.predicted_position = predicted_position; }

    public Integer getPredicted_position_with_market() { return predicted_position_with_market; }
    public void setPredicted_position_with_market(Integer predicted_position_with_market) { this.predicted_position_with_market = predicted_position_with_market; }

    public Integer getDriver_id() { return driver_id; }
    public void setDriver_id(Integer driver_id) { this.driver_id = driver_id; }

    public String getDriver_name() { return driver_name; }
    public void setDriver_name(String driver_name) { this.driver_name = driver_name; }

    public String getDriver_code() { return driver_code; }
    public void setDriver_code(String driver_code) { this.driver_code = driver_code; }

    public Integer getConstructor_id() { return constructor_id; }
    public void setConstructor_id(Integer constructor_id) { this.constructor_id = constructor_id; }

    public String getConstructor_name() { return constructor_name; }
    public void setConstructor_name(String constructor_name) { this.constructor_name = constructor_name; }

    public Integer getGrid() { return grid; }
    public void setGrid(Integer grid) { this.grid = grid; }

    public Integer getPosition() { return position; }
    public void setPosition(Integer position) { this.position = position; }

    public Double getPoints() { return points; }
    public void setPoints(Double points) { this.points = points; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public Double getForm_score() { return form_score; }
    public void setForm_score(Double form_score) { this.form_score = form_score; }

    public Double getPredicted_score() { return predicted_score; }
    public void setPredicted_score(Double predicted_score) { this.predicted_score = predicted_score; }

    public Double getWin_probability() { return win_probability; }
    public void setWin_probability(Double win_probability) { this.win_probability = win_probability; }

    public Double getMarket_probability() { return market_probability; }
    public void setMarket_probability(Double market_probability) { this.market_probability = market_probability; }

    public Double getFinal_probability() { return final_probability; }
    public void setFinal_probability(Double final_probability) { this.final_probability = final_probability; }

    public Double getReliability_rate() { return reliability_rate; }
    public void setReliability_rate(Double reliability_rate) { this.reliability_rate = reliability_rate; }

    public Double getConstructor_strength() { return constructor_strength; }
    public void setConstructor_strength(Double constructor_strength) { this.constructor_strength = constructor_strength; }

    public ScoreBreakdownDto getScore_breakdown() { return score_breakdown; }
    public void setScore_breakdown(ScoreBreakdownDto score_breakdown) { this.score_breakdown = score_breakdown; }
}
