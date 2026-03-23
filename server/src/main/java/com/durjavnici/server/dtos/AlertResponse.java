package com.durjavnici.server.dtos;
import java.time.Instant;

import com.durjavnici.server.models.Alert;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
@AllArgsConstructor
public class AlertResponse {
    private Long id;
    private String url;
    private Instant createdAt;

    public AlertResponse(Alert alert) {
        this.id = alert.getId();
        this.createdAt = alert.getCreatedAt();
        this.url = alert.getImage_url();
    }
}

