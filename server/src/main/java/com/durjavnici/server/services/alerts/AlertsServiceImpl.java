package com.durjavnici.server.services.alerts;

import java.io.IOException;
import java.util.Map;

import com.durjavnici.server.dtos.AlertResponse;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;

import com.durjavnici.server.dtos.AlertRequest;
import com.durjavnici.server.exceptions.InvalidTokenException;
import com.durjavnici.server.exceptions.UploadException;
import com.durjavnici.server.jwt.JwtProvider;
import com.durjavnici.server.models.Alert;
import com.durjavnici.server.repositories.AlertRepository;
import com.cloudinary.Cloudinary;
import com.cloudinary.utils.ObjectUtils;

import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class AlertsServiceImpl implements AlertsService{

    private final AlertRepository alertRepository;

    private final Cloudinary cloudinary;

    private final JwtProvider jwtProvider;


    @Override
    public Long createAlert(AlertRequest alertRequest, String token) {

        if(!jwtProvider.validateToken(token)) {
            throw new InvalidTokenException();
        }

        String url;
        String originalFilename = alertRequest.getFile().getOriginalFilename();
        System.out.println(originalFilename);

        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> uploadResult = cloudinary.uploader().upload(
                    alertRequest.getFile().getBytes(),
                    ObjectUtils.asMap(
                            "folder", "Alerts/documents",
                            "public_id", originalFilename + "_" + System.currentTimeMillis(),
                            "resource_type", "auto",
                            "overwrite", true)
            );

            url = (String) uploadResult.get("secure_url");
        } catch (IOException e) {
            throw new UploadException("Upload failed");
        }

        Alert alert = new Alert(url);

        alertRepository.save(alert);

        return alert.getId();
    }

    @Override
    public Page<AlertResponse> getAlerts(String token, Pageable pageable) {
        return alertRepository
                .findAll(pageable)
                .map(AlertResponse::new);
    }
}

