# ResQFlow 🚨
### Intelligent Disaster Response & Resource Coordination

ResQFlow is a disaster management prototype designed to improve emergency response through real-time vehicle tracking, resource monitoring, and adaptive route planning.

During disasters, coordinating emergency vehicles, relief resources, and affected locations can be challenging. ResQFlow aims to simplify these operations by providing a centralized platform that helps responders make faster and more informed decisions.

## 🌟 Key Features

- **Live Vehicle Tracking:** Monitor emergency vehicles using real-time GPS coordinates from driver devices.
- **Resource Monitoring:** Track resource availability and identify shortages at relief camps.
- **Smart Resource Allocation:** Coordinate emergency resource transfers between locations.
- **Dynamic Route Planning:** Identify alternative routes when roadblocks or disruptions affect existing routes.
- **Disaster Simulation:** Simulate disaster scenarios and observe resource shortages, vehicle movements, and response coordination.
- **Response Comparison:** Compare conventional manual coordination with ResQFlow-assisted response workflows.

## 🎯 Problem Statement

Disaster response operations often face challenges such as:
- Delayed emergency vehicle coordination.
- Limited visibility into resource availability.
- Difficulty identifying relief camp shortages.
- Road disruptions affecting emergency transportation.
- Inefficient communication between response teams.

## 💡 Our Solution

ResQFlow provides a centralized disaster response interface that connects vehicle tracking, resource coordination, and route planning.

The prototype demonstrates how real-time information and coordinated decision-making can support more efficient disaster response operations.

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| React | Frontend interface |
| Vite | Development and build tool |
| Tailwind CSS | UI styling |
| Node.js | Backend runtime |
| Express.js | Server framework |
| Socket.IO | Real-time communication |
| Python | Supporting application components |
| Geolocation API | Real phone GPS tracking |

## 🚀 Getting Started

### Prerequisites
- Node.js
- npm
- Python 3 (for Python components)

### Installation

```bash
git clone https://github.com/Yaswanth-Naidu07/ResQFlow.git
cd ResQFlow
npm install
```

### Run the Frontend

```bash
npm run dev
```

### Run the Real-Time Backend

```bash
node resqflow-realtime-server.cjs
```

Open the local URL displayed by Vite in your browser.

> Run the frontend and backend in separate terminals. Ensure the Socket.IO server is running for real-time tracking features.

## 📍 Live GPS Tracking

ResQFlow supports real phone location tracking through the browser's Geolocation API.

For GPS access:
- Open Driver Web on a GPS-enabled device.
- Allow location permission.
- Use HTTPS or localhost for secure geolocation access.
- Keep the device location enabled.

## 🧪 Prototype Demonstration

The prototype supports:
- Disaster scenario simulation.
- Resource shortage identification.
- Emergency vehicle dispatch.
- Live driver location updates.
- Route adaptation during road disruptions.
- Comparison of manual and coordinated response workflows.

## 🔮 Future Scope

- Integration with live disaster and weather data.
- AI-assisted disaster impact prediction.
- Automated resource allocation recommendations.
- Integration with emergency services.
- Advanced road network and traffic analysis.
- Multi-disaster response support.
- Volunteer and NGO coordination.
- Multilingual interface.



## 👥 Team

**CodeX**  
Ideathon 2026

---

*ResQFlow — Connecting resources, routes, and responders when every second matters.*
