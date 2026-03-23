package com.durjavnici.server.dtos;
import org.springframework.web.multipart.MultipartFile;

import lombok.Data;
import lombok.Getter;
import lombok.Setter;

@Data
@Getter
@Setter
public class AlertRequest {
    private MultipartFile file;
}
