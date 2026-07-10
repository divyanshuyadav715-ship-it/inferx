package com.inferx.gateway.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.connection.ReactiveRedisConnectionFactory;
import org.springframework.data.redis.listener.ReactiveRedisMessageListenerContainer;

@Configuration
public class RedisConfig {

    @Bean
    public ReactiveRedisMessageListenerContainer container(ReactiveRedisConnectionFactory factory) {
        // Exposes the listener container for reactive Pub/Sub subscriptions
        return new ReactiveRedisMessageListenerContainer(factory);
    }
}
