"""An Azure Python Pulumi program"""
import os
import pulumi
import pulumi_docker as docker
import pulumi_random as random
import pulumi_azure_native as azure_native
import pulumi_azuread as azuread


BASENAME = "streamlitpromptflowdemo"
IMAGE_NAME = "streamlitpromptflowdemo"
DOCKER_CONTEXT_PATH = "../"

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_API_BASE = os.environ["OPENAI_API_BASE"]

# Create an Azure Resource Group
resource_group = azure_native.resources.ResourceGroup(
    f"{BASENAME}-rg", location="uksouth")

suffix = random.RandomString(
    "suffix",
    length=5,
    special=False,
    upper=False,
    numeric=False,
)

# Create an Azure App Service Plan
app_service_plan = azure_native.web.AppServicePlan(
    f"{BASENAME}-app-service-plan",
    kind="linux",
    reserved=True,
    resource_group_name=resource_group.name,
    sku=azure_native.web.SkuDescriptionArgs(
        name="F1", tier="Free", size="F1", family="F", capacity=1
    ),
)

# Create an Azure Container Registry
registry = azure_native.containerregistry.Registry(
    f"{BASENAME}acr",
    admin_user_enabled=True,
    public_network_access=azure_native.containerregistry.PublicNetworkAccess.ENABLED,
    registry_name=pulumi.Output.concat(f"{BASENAME}acr", suffix.result),
    resource_group_name=resource_group.name,
    sku=azure_native.containerregistry.SkuArgs(
        name="Standard",
    ),
)


# Get the primary admin user access credentials for the registry
registry_credentials = pulumi.Output.all(
    resource_group.name, registry.name, registry.id
).apply(
    lambda args: azure_native.containerregistry.list_registry_credentials(
        args[1], args[0]
    )
)

# Get the password for the admin user
password = registry_credentials.apply(lambda c: c.passwords[0].value)

image_name = f"{IMAGE_NAME}:latest"
image_name_with_repo = pulumi.Output.all(registry.login_server).apply(
    lambda args: f"{args[0]}/{image_name}"
)

# Build and publish the Docker image to the registry
image = docker.Image(
    IMAGE_NAME,
    build=docker.DockerBuildArgs(
        context=DOCKER_CONTEXT_PATH,
    ),
    image_name=image_name_with_repo,
    registry=docker.RegistryArgs(
        server=registry.login_server,
        username=registry_credentials.username,
        password=registry_credentials.passwords[0].value,
    ),
)


webapp = azure_native.web.WebApp(
    resource_name="streamlit-promptflow-demo-webapp",
    resource_group_name=resource_group.name,
    client_affinity_enabled=False,
    enabled=True,
    https_only=True,
    key_vault_reference_identity="SystemAssigned",
    kind="app,linux,container",
    reserved=True,
    server_farm_id=app_service_plan.id,
    site_config=azure_native.web.SiteConfigArgs(
        always_on=False,
        http20_enabled=False,
        linux_fx_version=image_name_with_repo.apply(lambda i: f"DOCKER|{i}"),
        number_of_workers=1,
        app_command_line=""
    ),
)

current = azuread.get_client_config()

streamlit_promptflow_demo_aad_app = azuread.Application(
    "streamlit-promptflow-demo-aad-app",
    display_name="streamlit-promptflow-demo",
    sign_in_audience="AzureADMyOrg",
    owners=[current.object_id],
    web=azuread.ApplicationWebArgs(
        implicit_grant=azuread.ApplicationWebImplicitGrantArgs(
            id_token_issuance_enabled=True,
        ),
        redirect_uris=[
            pulumi.Output.concat(
                "https://",
                webapp.default_host_name,
                "/.auth/login/aad/callback",
            )
        ],
    ),
)


application_password = azuread.ApplicationPassword(
    "streamlit-promptflow-demo-aad-app-password",
    application_object_id=streamlit_promptflow_demo_aad_app.object_id,
)


azure_native.web.WebAppApplicationSettings(
    "streamlit-promptflow-demo-app-settings",
    resource_group_name=resource_group.name,
    name=webapp.name,
    kind="app",
    properties={
        "DOCKER_REGISTRY_SERVER_URL": pulumi.Output.concat(
            "https://", registry.login_server
        ),
        "DOCKER_REGISTRY_SERVER_USERNAME": registry.name,
        "DOCKER_REGISTRY_SERVER_PASSWORD": registry_credentials.passwords[0].value,
        "WEBSITES_ENABLE_APP_SERVICE_STORAGE": "false",
        "DOCKER_ENABLE_CI": "true",
        "WEBSITES_PORT": "8501",
        "OPENAI_API_KEY": OPENAI_API_KEY,
        "OPENAI_API_BASE": OPENAI_API_BASE,
        "CLIENT_SECRET": application_password.value,
    }
)

auth_settings = azure_native.web.WebAppAuthSettingsV2(
    "streamlit-promptflow-demo-auth-settings",
    name=webapp.name,
    resource_group_name=resource_group.name,
    identity_providers=azure_native.web.IdentityProvidersArgs(
        azure_active_directory=azure_native.web.AzureActiveDirectoryArgs(
            enabled=True,
            registration=azure_native.web.AzureActiveDirectoryRegistrationArgs(
                client_id=streamlit_promptflow_demo_aad_app.client_id,
                client_secret_setting_name="CLIENT_SECRET",
                open_id_issuer=f"https://sts.windows.net/{current.tenant_id}/v2.0"),
            validation=azure_native.web.AzureActiveDirectoryValidationArgs(
                allowed_audiences=[streamlit_promptflow_demo_aad_app.client_id]
                )
        )
    ),
    global_validation=azure_native.web.GlobalValidationArgs(
        unauthenticated_client_action=azure_native.web.UnauthenticatedClientActionV2.REDIRECT_TO_LOGIN_PAGE,
    )
)

pulumi.export("webapp_url", pulumi.Output.concat("https://", webapp.default_host_name))