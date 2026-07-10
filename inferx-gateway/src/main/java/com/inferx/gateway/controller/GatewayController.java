package com.inferx.gateway.controller;

import org.springframework.data.redis.connection.stream.MapRecord;
import org.springframework.data.redis.core.ReactiveRedisTemplate;
import org.springframework.data.redis.listener.ChannelTopic;
import org.springframework.data.redis.listener.ReactiveRedisMessageListenerContainer;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.Map;
import java.util.UUID;

@RestController
public class GatewayController {

    private final ReactiveRedisTemplate<String, String> redisTemplate;
    private final ReactiveRedisMessageListenerContainer redisMessageListenerContainer;

    public GatewayController(ReactiveRedisTemplate<String, String> redisTemplate, 
                             ReactiveRedisMessageListenerContainer redisMessageListenerContainer) {
        this.redisTemplate = redisTemplate;
        this.redisMessageListenerContainer = redisMessageListenerContainer;
    }

    @PostMapping(value = "/api/predict", consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    public Mono<ResponseEntity<String>> predict(@RequestBody String jsonRequest) {
        // Generate a unique Request ID for this inference task
        String reqId = UUID.randomUUID().toString();
        
        // Inject the ID into the JSON payload (simple string manipulation for demo)
        String payload = jsonRequest.replaceFirst("\\{", "{\"id\": \"" + reqId + "\", ");
        
        ChannelTopic topic = new ChannelTopic("channel:" + reqId);
        
        // 1. Subscribe to Redis Pub/Sub BEFORE publishing to stream to avoid race conditions
        Mono<String> resultMono = redisMessageListenerContainer.receive(topic)
                .next() // Only wait for the first message indicating completion
                .timeout(Duration.ofSeconds(30)) // 30s overall request timeout
                .flatMap(message -> {
                    // 4. Result Handling: Fetch the actual result from the Redis Hash
                    return redisTemplate.opsForHash().get("result:" + reqId, "data")
                            .map(Object::toString);
                })
                .doFinally(signal -> {
                    // Clean up the hash to prevent memory leaks in Redis
                    redisTemplate.opsForHash().remove("result:" + reqId, "data").subscribe();
                });
                
        // 2. Gateway pushes incoming requests to Redis Stream 'inferx_tasks' using XADD
        MapRecord<String, String, String> record = MapRecord.create("inferx_tasks", Map.of("payload", payload));
        return redisTemplate.opsForStream().add(record)
                .then(resultMono) // After pushing to stream, wait on the pub/sub listener
                .map(result -> ResponseEntity.ok(result))
                .onErrorResume(e -> Mono.just(ResponseEntity.status(503).body("{\"error\": \"Inference timed out or failed: " + e.getMessage() + "\"}")));
    }
}
