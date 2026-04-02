        $exceptions->report(function (\Throwable $e) {
            if (\ErrorMonitor\Monitor::hasClient()) {
                try {
                    \ErrorMonitor\capture_exception($e);
                } catch (\Throwable) {
                }
            }
        });
