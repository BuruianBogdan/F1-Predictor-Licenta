package com.f1predictor.frontendjava.dto;

import java.util.Map;

public class ScoreBreakdownDto {
    private Double form;
    private Double constructor_strength;
    private Double grid;
    private Double reliability;
    private Double points;
    private Double market;
    private Double penalty;

    public Double getForm() { return form; }
    public void setForm(Double form) { this.form = form; }

    public Double getConstructor_strength() { return constructor_strength; }
    public void setConstructor_strength(Double constructor_strength) { this.constructor_strength = constructor_strength; }

    public Double getGrid() { return grid; }
    public void setGrid(Double grid) { this.grid = grid; }

    public Double getReliability() { return reliability; }
    public void setReliability(Double reliability) { this.reliability = reliability; }

    public Double getPoints() { return points; }
    public void setPoints(Double points) { this.points = points; }

    public Double getMarket() { return market; }
    public void setMarket(Double market) { this.market = market; }

    public Double getPenalty() { return penalty; }
    public void setPenalty(Double penalty) { this.penalty = penalty; }
}
