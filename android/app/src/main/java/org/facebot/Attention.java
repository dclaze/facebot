package org.facebot;

import androidx.activity.ComponentActivity;
import androidx.camera.core.CameraSelector;
import androidx.camera.core.ImageAnalysis;
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

/** Presence only. No identity, emotion inference, tracking IDs or image persistence. */
final class Attention {
    interface Listener { void gaze(boolean present, float x, float y); }
    private final LifecycleCameraController camera;
    private final FaceDetector detector;
    private final ExecutorService analysis = Executors.newSingleThreadExecutor();
    Attention(ComponentActivity activity, PreviewView preview, Listener listener) {
        detector=FaceDetection.getClient(new FaceDetectorOptions.Builder()
            .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
            .setLandmarkMode(FaceDetectorOptions.LANDMARK_MODE_NONE)
            .setClassificationMode(FaceDetectorOptions.CLASSIFICATION_MODE_NONE).build());
        camera=new LifecycleCameraController(activity);
        camera.setCameraSelector(CameraSelector.DEFAULT_FRONT_CAMERA);
        camera.setEnabledUseCases(CameraController.IMAGE_ANALYSIS);
        camera.setImageAnalysisBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST);
        camera.setImageAnalysisAnalyzer(analysis,new MlKitAnalyzer(Collections.singletonList(detector),
            ImageAnalysis.COORDINATE_SYSTEM_VIEW_REFERENCED, ContextCompat.getMainExecutor(activity), result -> {
                List<Face> faces=result.getValue(detector);
                if(faces==null || faces.isEmpty() || preview.getWidth()==0 || preview.getHeight()==0) {
                    listener.gaze(false,.5f,.5f); return;
                }
                Face largest=faces.get(0);
                for(Face face:faces) if(face.getBoundingBox().width()>largest.getBoundingBox().width()) largest=face;
                // CameraController supplies preview coordinates, including lens transform.
                // Do not mirror or rotate them a second time.
                float x=largest.getBoundingBox().exactCenterX()/preview.getWidth();
                float y=largest.getBoundingBox().exactCenterY()/preview.getHeight();
                listener.gaze(true,Math.max(0,Math.min(1,x)),Math.max(0,Math.min(1,y)));
            }));
        preview.setController(camera);
        camera.bindToLifecycle(activity);
    }
    void close() { camera.clearImageAnalysisAnalyzer(); camera.unbind(); detector.close(); analysis.shutdown(); }
}
