package com.f1predictor.frontendjava.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.client.HttpStatusCodeException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import java.util.*;

@Service
public class FlaskApiService {
    private static final Logger log = LoggerFactory.getLogger(FlaskApiService.class);
    private final RestTemplate restTemplate;
    private final ObjectMapper mapper = new ObjectMapper();
    @Value("${flask.api.base-url}") private String baseUrl;
    @Value("${flask.api.admin-token:}") private String adminToken;
    public FlaskApiService() {
        var factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(3000); factory.setReadTimeout(120000);
        restTemplate = new RestTemplate(factory);
    }
    public String baseUrl() { return baseUrl; }
    public static class ApiException extends RuntimeException {
        private final int status;
        private final String code;
        public ApiException(String message) { this(message,503,"SERVICE_UNAVAILABLE"); }
        public ApiException(String message,int status,String code) { super(message);this.status=status;this.code=code; }
        public int getStatus() { return status; }
        public String getCode() { return code; }
    }
    private String call(String path, HttpMethod method, Object body) {
        try {
            HttpHeaders headers = new HttpHeaders(); headers.setContentType(MediaType.APPLICATION_JSON);
            if (adminToken != null && !adminToken.isBlank()) headers.setBearerAuth(adminToken);
            return restTemplate.exchange(baseUrl + path, method, new HttpEntity<>(body, headers), String.class).getBody();
        } catch (HttpStatusCodeException e) {
            log.warn("Backend {} returned {}", path, e.getStatusCode());
            try {
                var error = mapper.readTree(e.getResponseBodyAsString());
                String message = error.path("error").path("message").asText(error.path("message").asText("The requested data is unavailable."));
                throw new ApiException(message,e.getStatusCode().value(),error.path("error").path("code").asText("REQUEST_FAILED"));
            } catch (ApiException known) { throw known; }
            catch (Exception ignored) { throw new ApiException("The requested data is unavailable. Check Data status and try again.",e.getStatusCode().value(),"REQUEST_FAILED"); }
        } catch (Exception e) {
            log.warn("Backend request failed: {}", path, e);
            throw new ApiException("The data service is unavailable. Start the Flask backend and try again.");
        }
    }
    public List<Map<String,Object>> getList(String path) {
        try { return mapper.readValue(call(path,HttpMethod.GET,null),new TypeReference<List<Map<String,Object>>>(){}); }
        catch (ApiException e) { throw e; }
        catch (Exception e) { throw new ApiException("The data service returned an unreadable list."); }
    }
    public Map<String,Object> getMap(String path) { return parse(call(path,HttpMethod.GET,null)); }
    public Map<String,Object> postMap(String path,Object body) { return parse(call(path,HttpMethod.POST,body)); }
    public Map<String,Object> putMap(String path,Object body) { return parse(call(path,HttpMethod.PUT,body)); }
    private Map<String,Object> parse(String raw) {
        try { return mapper.readValue(raw,new TypeReference<Map<String,Object>>(){}); }
        catch(Exception e) { throw new ApiException("The data service returned an unreadable response."); }
    }
    public void delete(String path) { call(path,HttpMethod.DELETE,null); }
}
