package com.inferx.gateway.service;

import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.circuitbreaker.CircuitBreakerConfig;
import io.github.resilience4j.circuitbreaker.CircuitBreakerRegistry;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

@Service
public class LoadBalancerService {
    
    // Active Python ML worker nodes
    private final List<String> workerNodes = List.of(
            "http://localhost:8000",
            "http://localhost:8001",
            "http://localhost:8002"
    );
    
    private final Map<String, AtomicInteger> activeConnections = new ConcurrentHashMap<>();
    private final CircuitBreakerRegistry circuitBreakerRegistry;
    
    public LoadBalancerService() {
        // Configure Circuit Breaker: Trip on 50% failure rate, quarantine for 10 seconds
        CircuitBreakerConfig config = CircuitBreakerConfig.custom()
            .failureRateThreshold(50)
            .waitDurationInOpenState(Duration.ofSeconds(10))
            .slidingWindowSize(5)
            .build();
            
        this.circuitBreakerRegistry = CircuitBreakerRegistry.of(config);
        
        for (String node : workerNodes) {
            activeConnections.put(node, new AtomicInteger(0));
            circuitBreakerRegistry.circuitBreaker(node);
        }
    }
    
    public String getLeastConnectionsWorkerNode() {
        String bestNode = null;
        int minConnections = Integer.MAX_VALUE;
        
        for (String node : workerNodes) {
            CircuitBreaker cb = circuitBreakerRegistry.circuitBreaker(node);
            
            // Skip nodes where the circuit breaker is open (failing/quarantined)
            if (cb.getState() == CircuitBreaker.State.OPEN || cb.getState() == CircuitBreaker.State.FORCED_OPEN) {
                continue;
            }
            
            int connections = activeConnections.get(node).get();
            if (connections < minConnections) {
                minConnections = connections;
                bestNode = node;
            }
        }
        
        if (bestNode == null) {
            throw new RuntimeException("No healthy worker nodes available");
        }
        
        return bestNode;
    }
    
    public void incrementConnection(String node) {
        if (activeConnections.containsKey(node)) {
            activeConnections.get(node).incrementAndGet();
        }
    }
    
    public void decrementConnection(String node) {
        if (activeConnections.containsKey(node)) {
            activeConnections.get(node).decrementAndGet();
        }
    }
    
    public CircuitBreaker getCircuitBreaker(String node) {
        return circuitBreakerRegistry.circuitBreaker(node);
    }
}
