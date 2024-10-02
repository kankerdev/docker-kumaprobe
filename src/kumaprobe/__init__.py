import docker
import asyncio
import aiohttp
import uvloop
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

client = docker.DockerClient(base_url="unix://var/run/docker.sock")


async def send_health_status(endpoint, status):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(endpoint, json={"status": status}) as response:
                if response.status == 200:
                    logger.info(f"Successfully sent health status to {endpoint}")
                else:
                    logger.warning(
                        f"Received unexpected response {response.status} from {endpoint}"
                    )
        except Exception as e:
            logger.error(f"Failed to send health status to {endpoint}: {e}")


async def check_health_and_send(container_or_service):
    labels = container_or_service.attrs.get("Config", {}).get("Labels", {})

    # Check if there is a health label and an endpoint defined
    if "health" in labels and "kumaprobe.endpoint" in labels:
        health_status = container_or_service.attrs["State"]["Health"]["Status"]
        endpoint = labels["kumaprobe.endpoint"]

        # Only send the request if the service or container is healthy
        if health_status == "healthy":
            await send_health_status(endpoint, health_status)
        # Optionally log if not healthy
        else:
            logger.warning(
                f"{container_or_service.name} is not healthy: {health_status}"
            )


async def check_active_containers():
    containers = client.containers.list()
    return containers


async def check_active_services():
    services = client.services.list()
    return services


async def async_main():
    swarm_checked = False
    detected_services = set()
    detected_containers = set()

    # Initial check for swarm mode
    swarm_info = client.swarm.attrs
    swarm_state = swarm_info.get("State", {}).get("State", "inactive")

    if swarm_state == "active":
        logger.info("Swarm mode is active. Checking services.")
        services = await check_active_services()

        # Log initially detected services with labels starting with "kumaprobe"
        for service in services:
            labels = service.attrs.get("Spec", {}).get("Labels", {})
            if any(label.startswith("kumaprobe") for label in labels):
                detected_services.add(service.id)
                logger.info(f"Detected service with kumaprobe label: {service.name}")

    # Initial container check (after services)
    containers = await check_active_containers()
    for container in containers:
        labels = container.attrs.get("Config", {}).get("Labels", {})
        if any(label.startswith("kumaprobe") for label in labels):
            if (
                container.id not in detected_services
            ):  # Skip if already tracked as a service
                detected_containers.add(container.id)
                logger.info(
                    f"Detected container with kumaprobe label: {container.name}"
                )

    while True:
        # Check for new containers
        current_containers = await check_active_containers()
        for container in current_containers:
            labels = container.attrs.get("Config", {}).get("Labels", {})
            if any(label.startswith("kumaprobe") for label in labels):
                if (
                    container.id not in detected_containers
                    and container.id not in detected_services
                ):
                    detected_containers.add(container.id)
                    logger.info(
                        f"New container detected with kumaprobe label: {container.name}"
                    )

        # Check health of all containers
        for container in current_containers:
            await check_health_and_send(container)

        # Check for new services only once after the initial check
        if swarm_state == "active" and not swarm_checked:
            new_services = await check_active_services()
            for service in new_services:
                labels = service.attrs.get("Spec", {}).get("Labels", {})
                if any(label.startswith("kumaprobe") for label in labels):
                    if service.id not in detected_services:
                        detected_services.add(service.id)
                        logger.info(
                            f"New service detected with kumaprobe label: {service.name}"
                        )

            swarm_checked = True

        await asyncio.sleep(60)


def main():
    # Set uvloop as the event loop policy
    uvloop.install()
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
