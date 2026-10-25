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
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ConcurrentHashMap;

/** Presence only. No identity, emotion inference, tracking IDs or image persistence. */
final class Attention {
    interface Listener { void gaze(boolean present, float x, float y, String status, int faces, long analysisMs); }
    private final LifecycleCameraController camera;
    private final FaceDetector detector;
    private final ExecutorService analysis = Executors.newSingleThreadExecutor();
    private final ConcurrentHashMap<Long,Long> analysisStarted = new ConcurrentHashMap<>();
    Attention(ComponentActivity activity, PreviewView preview, Listener listener) {
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
                if(faces==null || faces.isEmpty() || preview.getWidth()==0 || preview.getHeight()==0) {
                    listener.gaze(false,.5f,.5f, faces==null ? "Vision unavailable" : "Vision: 0 visible faces", faces==null?-1:0, analysisMs); return;
                }
                Face largest=faces.get(0);
                for(Face face:faces) if(face.getBoundingBox().width()>largest.getBoundingBox().width()) largest=face;
                // CameraController supplies preview coordinates, including lens transform.
                // Do not mirror or rotate them a second time.
                float x=largest.getBoundingBox().exactCenterX()/preview.getWidth();
                float y=largest.getBoundingBox().exactCenterY()/preview.getHeight();
                listener.gaze(true,Math.max(0,Math.min(1,x)),Math.max(0,Math.min(1,y)),
                    "Vision: "+faces.size()+" visible face"+(faces.size()==1?"":"s"),faces.size(),analysisMs);
            });
        camera.setImageAnalysisAnalyzer(analysis, new ImageAnalysis.Analyzer() {
                @Override public int getTargetCoordinateSystem() { return mlkit.getTargetCoordinateSystem(); }
                @Override public android.util.Size getDefaultTargetResolution() { return mlkit.getDefaultTargetResolution(); }
                @Override public void updateTransform(android.graphics.Matrix matrix) { mlkit.updateTransform(matrix); }
                @Override public void analyze(ImageProxy image) {
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
