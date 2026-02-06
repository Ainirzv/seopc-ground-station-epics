#include <raylib.h>
#include <stdio.h>
#include <sys/stat.h>
#include <time.h>

#define IMAGE_PATH "../local_sync/latest_processed.jpg"

// Function to get file modification time
long GetLocalFileModTime(const char *path) {
    struct stat attr;
    if (stat(path, &attr) == 0) {
        return attr.st_mtime;
    }
    return 0;
}

int main(void) {
    const int screenWidth = 800;
    const int screenHeight = 600;

    InitWindow(screenWidth, screenHeight, "SEOPC - SOVEREIGN VIEW");

    // Load initial texture if available
    Texture2D texture = { 0 };
    long lastModTime = 0;
    bool textureLoaded = false;

    if (FileExists(IMAGE_PATH)) {
        Image img = LoadImage(IMAGE_PATH);
        texture = LoadTextureFromImage(img);
        UnloadImage(img);
        lastModTime = GetLocalFileModTime(IMAGE_PATH);
        textureLoaded = true;
    }

    SetTargetFPS(60);

    while (!WindowShouldClose()) {
        // Check for file update
        if (FileExists(IMAGE_PATH)) {
            long currentModTime = GetLocalFileModTime(IMAGE_PATH);
            if (currentModTime > lastModTime) {
                // Reload texture
                if (textureLoaded) UnloadTexture(texture);
                
                // Add a small delay/retry to ensure file write is complete by Python script
                 // Simple wait or just try loading. Raylib LoadImage is robust enough usually.
                Image img = LoadImage(IMAGE_PATH);
                texture = LoadTextureFromImage(img);
                UnloadImage(img);
                
                lastModTime = currentModTime;
                textureLoaded = true;
                printf("Texture reloaded from %s\n", IMAGE_PATH);
            }
        }

        BeginDrawing();

        ClearBackground(BLACK);

        if (textureLoaded) {
            // Draw texture scaled to fit window
            Rectangle source = { 0.0f, 0.0f, (float)texture.width, (float)texture.height };
            Rectangle dest = { 0.0f, 0.0f, (float)screenWidth, (float)screenHeight };
            Vector2 origin = { 0.0f, 0.0f };
            DrawTexturePro(texture, source, dest, origin, 0.0f, WHITE);
        } else {
            DrawText("WAITING FOR LINK...", 300, 300, 20, DARKGRAY);
        }

        // Draw UI Overlay
        DrawText("SECURE CONNECTION", 10, 10, 20, RED);

        EndDrawing();
    }

    if (textureLoaded) UnloadTexture(texture);
    CloseWindow();

    return 0;
}
