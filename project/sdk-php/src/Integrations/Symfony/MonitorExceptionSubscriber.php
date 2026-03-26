<?php

declare(strict_types=1);

namespace ErrorMonitor\Integrations\Symfony;

use ErrorMonitor\Client;
use Symfony\Component\EventDispatcher\EventSubscriberInterface;
use Symfony\Component\HttpKernel\Event\ExceptionEvent;
use Symfony\Component\HttpKernel\KernelEvents;

/**
 * services.yaml:
 *
 *   ErrorMonitor\Integrations\Symfony\MonitorExceptionSubscriber:
 *     arguments: ['@error_monitor.client']
 *     tags: [kernel.event_subscriber]
 *
 *   error_monitor.client:
 *     class: ErrorMonitor\Client
 *     arguments:
 *       - '%env(MONITOR_URL)%'
 *       - '%env(MONITOR_PROJECT_ID)%'
 *       - '%env(default::MONITOR_API_KEY)%'
 *       - null
 *       - { framework: symfony }
 */
final class MonitorExceptionSubscriber implements EventSubscriberInterface
{
    public function __construct(private readonly Client $client) {}

    public static function getSubscribedEvents(): array
    {
        return [KernelEvents::EXCEPTION => ['onKernelException', -128]];
    }

    public function onKernelException(ExceptionEvent $event): void
    {
        if (! $event->isMainRequest()) {
            return;
        }
        $req = $event->getRequest();
        $url = $req->getSchemeAndHttpHost() . $req->getRequestUri();
        try {
            $this->client->captureException($event->getThrowable(), [], $url);
        } catch (\Throwable) {
        }
    }
}
