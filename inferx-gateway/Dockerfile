# Stage 1: Build
FROM maven:3.9.6-eclipse-temurin-22 AS builder
WORKDIR /app
COPY pom.xml .
# Download dependencies (go-offline) to cache them
RUN mvn dependency:go-offline -B
# Copy source code and build the application
COPY src ./src
RUN mvn clean package -DskipTests

# Stage 2: Runtime
FROM eclipse-temurin:22-jre-alpine
WORKDIR /app

# Create a non-root user for security best practices
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

# Copy only the compiled .jar file from the builder stage
COPY --from=builder /app/target/*.jar app.jar

EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
