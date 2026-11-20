package org.nexusai.panel;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.time.format.DateTimeFormatter;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final String HOST = "192.168.1.238";
    private static final int PORT = 18767;
    private static final String BASE_URL = "http://" + HOST + ":" + PORT;
    private static final int BACKGROUND = Color.rgb(18, 15, 20);
    private static final int FOREGROUND = Color.rgb(246, 238, 241);
    private static final int ONLINE = Color.rgb(148, 225, 202);
    private static final int OFFLINE = Color.rgb(255, 120, 143);
    private static final DateTimeFormatter ATHENS_TIME =
        DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm:ss");

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Runnable poll = new Runnable() {
        @Override public void run() {
            refreshStatus();
            handler.postDelayed(this, 5000);
        }
    };
    private boolean statusApp;
    private boolean foreground;
    private WebView web;
    private TextView status;
    private TextView information;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        statusApp = getPackageName().endsWith(".backend");
        if (statusApp) showBackend();
        else showDashboard(pairingPath(getIntent()));
        fullscreen();
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        String path = pairingPath(intent);
        if (!statusApp && !"/".equals(path) && web != null) web.loadUrl(BASE_URL + path);
    }

    private String pairingPath(Intent intent) {
        String ticket = intent.getStringExtra("nexus_spotify_pair");
        intent.removeExtra("nexus_spotify_pair");
        if (ticket != null && ticket.matches("[A-Za-z0-9_-]{43}")) return "/#spotify-pair=" + ticket;
        return "/";
    }

    @Override public void onWindowFocusChanged(boolean focused) {
        super.onWindowFocusChanged(focused);
        if (focused) fullscreen();
    }

    @Override protected void onResume() {
        super.onResume();
        foreground = true;
        if (statusApp) handler.post(poll);
    }

    @Override protected void onPause() {
        foreground = false;
        handler.removeCallbacks(poll);
        super.onPause();
    }

    @Override protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        executor.shutdownNow();
        if (web != null) web.destroy();
        super.onDestroy();
    }

    private void fullscreen() {
        getWindow().getDecorView().setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_LAYOUT_STABLE | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        );
    }

    private void showDashboard(String path) {
        if (web != null) web.destroy();
        web = new WebView(this);
        web.setBackgroundColor(BACKGROUND);
        web.getSettings().setJavaScriptEnabled(true);
        web.getSettings().setDomStorageEnabled(true);
        web.getSettings().setAllowFileAccess(false);
        web.getSettings().setAllowContentAccess(false);
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri url = request.getUrl();
                return !("http".equals(url.getScheme()) && HOST.equals(url.getHost()) && url.getPort() == PORT);
            }

            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    LinearLayout panel = panel();
                    label(panel, "NEXUS AI · Dashboard", 30, FOREGROUND);
                    label(panel, "Το dashboard δεν απαντά.", 19, OFFLINE);
                    Button retry = new Button(MainActivity.this);
                    retry.setText("Δοκίμασε ξανά");
                    retry.setOnClickListener(v -> showDashboard(path));
                    panel.addView(retry);
                    setContentView(panel);
                }
            }
        });
        setContentView(web);
        web.loadUrl(BASE_URL + path);
    }

    private LinearLayout panel() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setGravity(Gravity.CENTER);
        int padding = (int) (getResources().getDisplayMetrics().density * 28);
        layout.setPadding(padding, padding, padding, padding);
        layout.setBackgroundColor(BACKGROUND);
        return layout;
    }

    private TextView label(LinearLayout parent, String text, int size, int color) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setGravity(Gravity.CENTER);
        view.setTextSize(size);
        view.setTextColor(color);
        view.setPadding(0, 12, 0, 12);
        parent.addView(view);
        return view;
    }

    private void showBackend() {
        LinearLayout panel = panel();
        label(panel, "NEXUS AI · Backend", 34, FOREGROUND);
        status = label(panel, "Έλεγχος υπηρεσίας…", 25, ONLINE);
        status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        information = label(panel, "", 17, FOREGROUND);
        setContentView(panel);
    }

    private void refreshStatus() {
        executor.execute(() -> {
            HttpURLConnection connection = null;
            try {
                connection = (HttpURLConnection) new URL(BASE_URL + "/api/status").openConnection();
                connection.setConnectTimeout(1800);
                connection.setReadTimeout(2500);
                connection.setInstanceFollowRedirects(false);
                if (connection.getResponseCode() != 200) throw new IllegalStateException("Status unavailable");
                ByteArrayOutputStream body = new ByteArrayOutputStream();
                try (InputStream input = connection.getInputStream()) {
                    byte[] buffer = new byte[1024];
                    int read;
                    while ((read = input.read(buffer)) != -1) {
                        body.write(buffer, 0, read);
                        if (body.size() > 8192) throw new IllegalStateException("Invalid status payload");
                    }
                }
                JSONObject data = new JSONObject(new String(body.toByteArray(), StandardCharsets.UTF_8));
                if (!data.getBoolean("backend")) throw new IllegalStateException("Backend offline");
                String started = OffsetDateTime.parse(data.getString("started")).format(ATHENS_TIME);
                String details = "Συλλέκτης Ubuntu: " + (data.getBoolean("collector") ? "Συνδεδεμένος" : "Δεν απαντά")
                    + "\nΈναρξη: " + started + " · Ώρα Αθήνας"
                    + "\nΕγκεκριμένες αναφορές: " + data.getInt("reports");
                handler.post(() -> showStatus("Σε λειτουργία", ONLINE, details));
            } catch (Exception error) {
                handler.post(() -> showStatus("Εκτός σύνδεσης", OFFLINE,
                    "Το πάνελ επανελέγχει αυτόματα κάθε 5 δευτερόλεπτα."));
            } finally {
                if (connection != null) connection.disconnect();
            }
        });
    }

    private void showStatus(String title, int color, String details) {
        if (!foreground) return;
        if (!title.contentEquals(status.getText())) status.setText(title);
        status.setTextColor(color);
        if (!details.contentEquals(information.getText())) information.setText(details);
    }
}
