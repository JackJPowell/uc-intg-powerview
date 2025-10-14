[![Discord](https://badgen.net/discord/online-members/zGVYf58)](https://discord.gg/zGVYf58)
![GitHub Release](https://img.shields.io/github/v/release/jackjpowell/uc-intg-powerview)
![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/jackjpowell/uc-intg-powerview/total)
![Maintenance](https://img.shields.io/maintenance/yes/2025.svg)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy_Me_A_Coffee☕-FFDD00?logo=buy-me-a-coffee&logoColor=white&labelColor=grey)](https://buymeacoffee.com/jackpowell)

# Hunter Douglas PowerView Integration for Unfolded Circle Remotes

Control your Hunter Douglas PowerView motorized shades and scenes directly from your Unfolded Circle Remote Two or Remote 3. This integration features **dynamic entity discovery**, automatic reconnection, and comprehensive shade control. Powered by [uc-integration-api](https://github.com/aitatoi/integration-python-library).

---

## Table of Contents

- [Features](#features)
- [Supported Devices](#supported-devices)
- [Requirements](#requirements)
- [Installation](#installation)
- [Setup & Configuration](#setup--configuration)
- [Usage](#usage)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

---

## Features

### 🎯 **Dynamic Entity Discovery**
- Automatically discovers all shades and scenes from your PowerView hub
- No need to manually configure individual shades
- Entities are refreshed on each connection

### 🪟 **Shade Control (Cover Entities)**
- **Open** - Fully open shades
- **Close** - Fully close shades  
- **Stop** - Stop shade movement mid-operation
- **Position** - Set precise shade position (0-100%)
- Real-time position feedback

### 🎬 **Scene Activation (Button Entities)**
- Trigger PowerView scenes directly from your remote
- Activate multiple shades with pre-configured positions
- Perfect for "Good Morning", "Movie Time", or custom scenes

### 🔄 **Automatic Reconnection**
- Built-in watchdog monitors connection health
- Automatically reconnects if hub becomes unavailable
- Graceful error handling and recovery

### 🏠 **Multi-Hub Support**
- Control shades from multiple PowerView hubs
- Manage different rooms or properties
- Each hub configured independently

---

## Supported Devices

### ✅ **PowerView Hubs**
- **PowerView Hub (Gen 2)** - The square hub with ethernet
- **PowerView Hub (Gen 3)** - The new smaller hub
- Any hub running PowerView firmware

### ✅ **Motorized Shades**
All Hunter Douglas PowerView motorized window treatments:
- Duette® Honeycomb Shades
- Silhouette® Shades
- Vignette® Modern Roman Shades
- Pirouette® Shades
- Solera® Soft Shades
- Luminette® Privacy Sheers
- Designer Roller Shades
- Designer Screen Shades
- Palm Beach™ Shutters
- Any other PowerView-compatible motorized shades

> **Note:** Shades must be paired with a PowerView Hub to be controlled by this integration.

---

## Requirements

- **Unfolded Circle Remote Two** or **Remote 3** (firmware >= 2.0.0)
- **Hunter Douglas PowerView Hub** (Gen 2 or Gen 3)
- **Network Connection** - Hub and remote on the same local network

---

## Installation

### Unfolded Circle Remote

1. **Download** the latest `.tar.gz` release from the [Releases](https://github.com/JackJPowell/uc-intg-powerview/releases) page.
2. **Upload** the file via the Integrations tab in your remote's web configurator (requires firmware >= 2.0.0).

### Docker

```sh
docker run -d \
  --name=uc-intg-powerview \
  --network host \
  -v $(pwd)/<local_directory>:/config \
  --restart unless-stopped \
  ghcr.io/jackjpowell/uc-intg-powerview:latest
```

### Docker Compose

```yaml
services:
  uc-intg-powerview:
    image: ghcr.io/jackjpowell/uc-intg-powerview:latest
    container_name: uc-intg-powerview
    network_mode: host
    volumes:
      - ./<local_directory>:/config
    environment:
      - UC_INTEGRATION_HTTP_PORT=9090   # Optional: set custom HTTP port
      - UC_LOG_LEVEL=INFO                # Optional: DEBUG, INFO, WARNING, ERROR
    restart: unless-stopped
```

---

## Setup & Configuration

### First-Time Setup

1. **Open Web Configurator**  
   Navigate to your Remote Two/3's web interface (usually \`http://remote-ip\`)

2. **Add Integration**  
   - Go to **Integrations** → **Add Integration**
   - Select **Hunter Douglas PowerView** from the list

3. **Hub Discovery**  
   The integration will automatically scan your network for PowerView hubs.
   
   **Option A - Automatic Discovery:**
   - Select your hub from the discovered devices list
   - Click **Next**
   
   **Option B - Manual Entry:**
   - Click **Manual Entry**
   - Enter your PowerView Hub's IP address (e.g., \`192.168.1.100\`)
   - Click **Next**

4. **Connection & Discovery**  
   - The integration will connect to your hub
   - All shades and scenes are automatically discovered
   - Entity registration happens in real-time

5. **Complete Setup**  
   - Review the discovered entities
   - Click **Finish**
   - Your shades and scenes are now available!

### Adding Multiple Hubs

You can add multiple PowerView hubs (e.g., for different floors or properties):

1. Go to **Integrations** → **Hunter Douglas PowerView** → **⋮** (Options)
2. Select **Reconfigure**
3. Choose **Add a new hub**
4. Follow the setup process for the new hub

### Reconfiguration

To modify or remove hubs:

1. Go to **Integrations** → **Hunter Douglas PowerView** → **⋮** (Options)
2. Select **Reconfigure**
3. Choose an option:
   - **Add a new hub** - Add another PowerView hub
   - **Remove a hub** - Delete a hub configuration
   - **Reset** - Clear all configurations and start over

---

## Usage

### Controlling Shades

Once configured, your shades appear as **Cover entities** on your remote:

**Via Remote UI:**
- **Open/Close buttons** - Tap to open or close
- **Position slider** - Drag to set precise position (0-100%)
- **Stop button** - Tap to stop shade movement

**Via Activities:**
- Add shade control to custom activities
- Set shade positions for "Watch Movie", "Good Night", etc.
- Combine with lights, media, and other devices

### Activating Scenes

PowerView scenes appear as **Button entities**:

**Via Remote UI:**
- Tap a scene button to activate
- All shades in the scene move to pre-configured positions

**Via Activities:**
- Add scenes to activity sequences
- Create custom automations
- "Good Morning" scene + lights + music

### Tips & Best Practices

💡 **Use Scenes for Complex Control**  
Instead of controlling individual shades, create scenes in the PowerView app and trigger them from your remote.

💡 **Network Stability**  
For best performance, ensure your PowerView hub has a stable network connection (wired ethernet recommended for Gen 2 hubs).

💡 **Firmware Updates**  
Keep your PowerView hub firmware updated via the PowerView app for best compatibility.

---

## Contributing

Contributions are always welcome! Whether it's bug reports, feature requests, or code contributions.

### How to Contribute

1. **Report Issues**  
   Found a bug? [Open an issue](https://github.com/JackJPowell/uc-intg-powerview/issues/new) with:
   - Clear description of the problem
   - Steps to reproduce
   - Expected vs actual behavior
   - Integration version and remote firmware

2. **Suggest Features**  
   Have an idea? [Open a feature request](https://github.com/JackJPowell/uc-intg-powerview/issues/new) with:
   - Description of the feature
   - Use case / why it's useful
   - Any implementation ideas

3. **Submit Pull Requests**  
   - Fork the repository
   - Create a feature branch (\`git checkout -b feature/amazing-feature\`)
   - Make your changes
   - Test thoroughly
   - Commit with clear messages
   - Push to your fork
   - Open a Pull Request

### Development Setup

\`\`\`bash
# Clone the repository
git clone https://github.com/JackJPowell/uc-intg-powerview.git
cd uc-intg-powerview

# Install dependencies
pip install -r requirements.txt

# Run the integration
python intg-powerview/driver.py
\`\`\`


---

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.

## Acknowledgments

- **Unfolded Circle** - For creating the Remote Two/3 and the integration API
- **[uc-integration-api](https://github.com/aitatoi/integration-python-library)** - Python library that powers this integration
- **[aiopvapi](https://github.com/sander76/aio-powerview-api)** - Async PowerView API library

---

## Support

### Get Help

- 💬 **[Discord Community](https://discord.gg/zGVYf58)** - Chat with other users, ask questions, share tips
- 🐛 **[GitHub Issues](https://github.com/JackJPowell/uc-intg-powerview/issues)** - Report bugs or request features

### Show Your Support

If this integration has been helpful, consider:

- ⭐ **Star this repository** - Helps others discover the project
- ☕ **[Buy Me a Coffee](https://buymeacoffee.com/jackpowell)** - Support ongoing development
- 🗣️ **Share** - Tell others about the integration
- 🤝 **Contribute** - Submit bug fixes or features

---

**Made with ❤️ by [Jack Powell](https://github.com/jackjpowell)**

*Control your shades the smart way!* 🪟✨
