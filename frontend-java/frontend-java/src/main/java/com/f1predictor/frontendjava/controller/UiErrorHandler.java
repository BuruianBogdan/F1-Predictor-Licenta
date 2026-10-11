package com.f1predictor.frontendjava.controller;
import com.f1predictor.frontendjava.service.FlaskApiService.ApiException;
import org.springframework.web.bind.annotation.*;
import org.springframework.ui.Model;
import org.springframework.http.HttpStatus;
@ControllerAdvice
public class UiErrorHandler {
    @ExceptionHandler(ApiException.class)
    @ResponseStatus(HttpStatus.SERVICE_UNAVAILABLE)
    public String apiError(ApiException exception, Model model) {
        model.addAttribute("friendlyError",exception.getMessage()); return "service-error";
    }
}
