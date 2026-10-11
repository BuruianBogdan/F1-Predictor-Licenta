package com.f1predictor.frontendjava.controller;

import com.f1predictor.frontendjava.service.FlaskApiService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Map;
import java.util.Set;

/** The Tools update action uses the existing Race Control services. */
@Controller
public class SessionRefreshController {
    private final FlaskApiService api;
    @Value("${flask.api.admin-token:}") private String adminToken;
    public SessionRefreshController(FlaskApiService api) { this.api = api; }

    @GetMapping("/race-control/api/sessions/refresh") @ResponseBody
    public ResponseEntity<Map<String,Object>> status() {
        try { return ResponseEntity.ok(api.getMap("/race-control/sessions/refresh")); }
        catch (FlaskApiService.ApiException e) { return error(e); }
    }

    @PostMapping("/race-control/api/sessions/refresh") @ResponseBody
    public ResponseEntity<Map<String,Object>> refresh(HttpServletRequest request, @RequestBody(required=false) Map<String,Object> body) {
        String origin = request.getHeader("Origin");
        if (origin != null && !origin.equals("http://127.0.0.1:" + request.getServerPort()) && !origin.equals("http://localhost:" + request.getServerPort()))
            return ResponseEntity.status(403).body(Map.of("error", Map.of("message", "Cross-origin administration is not permitted")));
        boolean local = Set.of("127.0.0.1", "::1", "0:0:0:0:0:0:0:1").contains(request.getRemoteAddr());
        boolean token = adminToken != null && !adminToken.isBlank() && MessageDigest.isEqual(("Bearer " + adminToken).getBytes(StandardCharsets.UTF_8), String.valueOf(request.getHeader("Authorization")).getBytes(StandardCharsets.UTF_8));
        if (!local && !token)
            return ResponseEntity.status(403).body(Map.of("error", Map.of("message", "Session refresh is local or token-authorized only")));
        try { return ResponseEntity.accepted().body(api.postMap("/race-control/sessions/refresh", body == null ? Map.of() : body)); }
        catch (FlaskApiService.ApiException e) { return error(e); }
    }

    private ResponseEntity<Map<String,Object>> error(FlaskApiService.ApiException e) {
        return ResponseEntity.status(e.getStatus()).body(Map.of("error", Map.of("code", e.getCode(), "message", e.getMessage())));
    }
}
