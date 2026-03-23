package com.durjavnici.server.controllers;

import com.durjavnici.server.jwt.JwtProvider;
import org.apache.http.HttpStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.web.PageableDefault;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.durjavnici.server.dtos.ApiResponse;
import com.durjavnici.server.dtos.AlertRequest;
import com.durjavnici.server.dtos.AlertResponse;
import com.durjavnici.server.services.alerts.AlertsService;

import lombok.RequiredArgsConstructor;

@RestController
@RequestMapping("/api/alert")
@RequiredArgsConstructor
public class AlertController {
    private final JwtProvider jwtProvider;
    private final AlertsService alertsService;

    @PostMapping(value = "/", consumes = "multipart/form-data")
    public ResponseEntity<ApiResponse> uploadAlert(
            @ModelAttribute AlertRequest request, @RequestHeader("Authorization") String authHeader) {
        String token = jwtProvider.extractTokenFromHeader(authHeader);

        Long id = alertsService.createAlert(request, token);

        return ResponseEntity.ok(new ApiResponse(HttpStatus.SC_CREATED, "Alert created successfully", id));
    }

    @GetMapping("/")
    public ResponseEntity<ApiResponse> getAlerts(
            @RequestHeader("Authorization") String authHeader,
            @PageableDefault Pageable pageable
    ) {
        String token = jwtProvider.extractTokenFromHeader(authHeader);

        Page<AlertResponse> alerts = alertsService.getAlerts(token, pageable);;

        ApiResponse response = new ApiResponse(
                HttpStatus.SC_OK,
                "Alerts retrieved successfully",
                alerts
        );

        return ResponseEntity.ok(response);
    }
}
