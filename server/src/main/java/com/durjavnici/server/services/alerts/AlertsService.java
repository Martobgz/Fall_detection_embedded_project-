package com.durjavnici.server.services.alerts;

import com.durjavnici.server.dtos.AlertRequest;
import com.durjavnici.server.dtos.AlertResponse;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;

public interface AlertsService {
    Long createAlert(AlertRequest alertRequest, String token);
    Page<AlertResponse> getAlerts(String token, Pageable pageable);
}
