package com.f1predictor.frontendjava.service;

import com.f1predictor.frontendjava.dto.ChampionPredictionDto;
import com.f1predictor.frontendjava.dto.RacePredictionResponseDto;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.*;

@Service
public class PredictionApiService {
    private final RestTemplate restTemplate = new RestTemplate();

    @Value("${flask.api.base-url}")
    private String flaskBaseUrl;

    public List<ChampionPredictionDto> getChampionPrediction() {
        ResponseEntity<List<ChampionPredictionDto>> response = restTemplate.exchange(
                flaskBaseUrl + "/predict/champion",
                HttpMethod.GET,
                null,
                new ParameterizedTypeReference<List<ChampionPredictionDto>>() {}
        );
        return response.getBody() != null ? response.getBody() : new ArrayList<>();
    }

    public RacePredictionResponseDto getRacePrediction(Integer raceId, int limit) {
        return restTemplate.getForObject(
                flaskBaseUrl + "/predict/race/" + raceId + "/summary?limit=" + limit,
                RacePredictionResponseDto.class
        );
    }

    public RacePredictionResponseDto getRacePredictionFull(Integer raceId) {
        return restTemplate.getForObject(
                flaskBaseUrl + "/predict/race/" + raceId,
                RacePredictionResponseDto.class
        );
    }

    public RacePredictionResponseDto getRacePredictionWithMarket(Integer raceId, List<Map<String, Object>> odds) {
        Map<String, Object> body = new HashMap<>();
        body.put("odds", odds != null ? odds : List.of());

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Map<String, Object>> request = new HttpEntity<>(body, headers);

        ResponseEntity<RacePredictionResponseDto> response = restTemplate.exchange(
                flaskBaseUrl + "/predict/race/" + raceId + "/market",
                HttpMethod.POST,
                request,
                RacePredictionResponseDto.class
        );
        return response.getBody();
    }

    public Map<String, Object> getModelExplanation() {
        Map<?, ?> raw = restTemplate.getForObject(flaskBaseUrl + "/predict/explain", Map.class);
        if (raw == null) {
            return Map.of();
        }
        Map<String, Object> result = new HashMap<>();
        raw.forEach((k, v) -> result.put(String.valueOf(k), v));
        return result;
    }
}
