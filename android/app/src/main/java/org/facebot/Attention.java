package org.facebot;

import androidx.activity.ComponentActivity;
import androidx.camera.core.CameraSelector;
import androidx.camera.core.ImageAnalysis;
import androidx.camera.core.ImageProxy;
import androidx.camera.mlkit.vision.MlKitAnalyzer;
import androidx.camera.view.CameraController;
import androidx.camera.view.LifecycleCameraController;
import androidx.camera.view.PreviewView;
import androidx.core.content.ContextCompat;
import com.google.mlkit.vision.face.Face;
import com.google.mlkit.vision.face.FaceDetection;
import com.google.mlkit.vision.face.FaceDetector;
import com.google.mlkit.vision.face.FaceDetectorOptions;
import java.util.Collections;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ConcurrentHashMap;

/** Ephemeral group positions only. No identity, emotion inference or image persistence. */
final class Attention {
    interface Listener { void gaze(boolean present, float x, float y, String status, int faces, long analysisMs, int faceFill); }
    private final GroupAttention group = new GroupAttention();
    private final LifecycleCameraController camera;
    private final FaceDetector detector;
    private final ExecutorService analysis = Executors.newSingleThreadExecutor();
    private final ConcurrentHashMap<Long,Long> analysisStarted = new ConcurrentHashMap<>();
    Attention(ComponentActivity activity, PreviewView preview, Listener listener, java.util.function.Consumer<ImageProxy> snapshot) {
        detector=FaceDetection.getClient(new FaceDetectorOptions.Builder()
            .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
            .setLandmarkMode(FaceDetectorOptions.LANDMARK_MODE_NONE)
            .setClassificationMode(FaceDetectorOptions.CLASSIFICATION_MODE_NONE).build());
        camera=new LifecycleCameraController(activity);
        camera.setCameraSelector(CameraSelector.DEFAULT_FRONT_CAMERA);
        camera.setEnabledUseCases(CameraController.IMAGE_ANALYSIS);
        camera.setImageAnalysisBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST);
        final MlKitAnalyzer mlkit = new MlKitAnalyzer(Collections.singletonList(detector),
            ImageAnalysis.COORDINATE_SYSTEM_VIEW_REFERENCED, ContextCompat.getMainExecutor(activity), result -> {
                List<Face> faces=result.getValue(detector);
                Long started=analysisStarted.remove(result.getTimestamp());
                long analysisMs=started==null?10001:Math.max(0,(System.nanoTime()-started)/1000000);
                long now=android.os.SystemClock.elapsedRealtime();
                List<GroupAttention.Box> positions=new ArrayList<>();
                boolean valid=faces!=null && preview.getWidth()>0 && preview.getHeight()>0 && analysisMs<=500;
                float largestFill=0;
                if(valid) for(Face face:faces) {
                    android.graphics.Rect box=face.getBoundingBox();
                    // CameraController already maps to preview coordinates.
                    positions.add(new GroupAttention.Box(box.exactCenterX()/preview.getWidth(),
                        box.exactCenterY()/preview.getHeight(),(float)box.width()*box.height()));
                    largestFill=Math.max(largestFill,Math.min(1f,(float)box.width()*box.height()/(preview.getWidth()*preview.getHeight())));
                }
                group.update(positions,now);
                int count=valid?faces.size():-1;
                String status=count<0?"Vision unavailable": "Vision: "+count+" visible face"+(count==1?"":"s")+" / group gaze";
                // Brief occlusion holds a position; expires to neutral, never a speaker claim.
                listener.gaze(group.size()>0,group.x(),group.y(),status,count,analysisMs,Math.round(largestFill*1000));
            });
        camera.setImageAnalysisAnalyzer(analysis, new ImageAnalysis.Analyzer() {
                @Override public int getTargetCoordinateSystem() { return mlkit.getTargetCoordinateSystem(); }
                @Override public android.util.Size getDefaultTargetResolution() { return mlkit.getDefaultTargetResolution(); }
                @Override public void updateTransform(android.graphics.Matrix matrix) { mlkit.updateTransform(matrix); }
                @Override public void analyze(ImageProxy image) {
                    snapshot.accept(image);
                    if (analysisStarted.size()>8) analysisStarted.clear();
                    analysisStarted.put(image.getImageInfo().getTimestamp(),System.nanoTime());
                    mlkit.analyze(image);
                }
            });
        preview.setController(camera);
        camera.bindToLifecycle(activity);
    }
    void close() { camera.clearImageAnalysisAnalyzer(); camera.unbind(); detector.close(); analysis.shutdown(); }
}
