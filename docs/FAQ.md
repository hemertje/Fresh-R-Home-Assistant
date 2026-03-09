# Fresh-r Integration FAQ

## 🇬🇧 English FAQ

### **Q: How do I install the Fresh-r integration?**
A: Download the latest `fresh_r_system.zip` from the [GitHub releases](https://github.com/hemertje/Fresh-R-Home-Assistant/releases) and follow the installation steps in the README.

### **Q: The integration is not finding my devices**
A: Make sure you're using the correct email and password for your fresh-r.me account. Check the debug logs for more information.

### **Q: How often does the integration update?**
A: Default is every 60 seconds, minimum is 30 seconds. You can configure this in the integration settings.

### **Q: Can I control my Fresh-r device through this integration?**
A: No, this is a read-only integration. The Fresh-r firmware does not expose control endpoints.

### **Q: What sensors are available?**
A: 20 sensors including temperatures, flow, CO2, humidity, dew point, particulate matter, heat recovery, and energy loss.

### **Q: How do I enable MQTT or InfluxDB?**
A: During integration setup, enable the "Publish to MQTT" and/or "Write to InfluxDB" options and configure your broker/database settings.

### **Q: The Lovelace card shows "No data"**
A: Make sure the integration is running and sensors are available. Check the integration status in Home Assistant.

### **Q: How do I change the language of the interface?**
A: Set your preferred language in Home Assistant: `Settings → Profile → Language`. The integration will automatically detect and use your language preference.

### **Q: What languages are supported?**
A: English, Dutch, German, and French are fully supported for both the config flow and Lovelace card.

### **Q: I'm getting authentication errors**
A: Check your fresh-r.me credentials and make sure your account is active. The integration requires the same credentials as the fresh-r.me web dashboard.

### **Q: How do I troubleshoot connection issues?**
A: Enable debug logging in your `configuration.yaml`:
```yaml
logger:
  default: warning
  logs:
    custom_components.fresh_r: debug
```

### **Q: Can I use this with multiple Fresh-r devices?**
A: Yes, the integration will automatically discover all Fresh-r devices associated with your account.

### **Q: What is the rate limiting for API calls?**
A: The integration uses safe intervals: 12 login requests per hour and 4 data requests per hour maximum.

### **Q: How do I import the Grafana dashboard?**
A: In Grafana, go to `Dashboards → Import → Upload JSON file` and select the `fresh_r_dashboard.json` from the ZIP file.

---

## 🇳🇱 Nederlandse FAQ

### **V: Hoe installeer ik de Fresh-r integratie?**
A: Download de laatste `fresh_r_system.zip` van de [GitHub releases](https://github.com/hemertje/Fresh-R-Home-Assistant/releases) en volg de installatiestappen in de README.

### **V: De integratie vindt mijn apparaten niet**
A: Zorg ervoor dat je de juiste e-mail en wachtwoord voor je fresh-r.me account gebruikt. Controleer de debug logs voor meer informatie.

### **V: Hoe vaak werkt de integratie bij?**
A: Standaard elke 60 seconden, minimum is 30 seconden. Je kunt dit instellen in de integratie-instellingen.

### **V: Kan ik mijn Fresh-r apparaat besturen via deze integratie?**
A: Nee, dit is een read-only integratie. De Fresh-r firmware biedt geen control endpoints.

### **V: Welke sensoren zijn beschikbaar?**
A: 20 sensoren inclusief temperaturen, debiet, CO2, vochtigheid, dauwpunt, fijnstof, warmteterugwinning en energieverlies.

### **V: Hoe schakel ik MQTT of InfluxDB in?**
A: Tijdens integratie-setup, schakel "MQTT publiceren" en/of "InfluxDB schrijven" in en configureer je broker/database instellingen.

### **V: De Lovelace kaart toont "Geen data"**
A: Zorg ervoor dat de integratie actief is en sensoren beschikbaar zijn. Controleer de integratie status in Home Assistant.

### **V: Hoe verander ik de taal van de interface?**
A: Stel je voorkeurstaal in Home Assistant: `Instellingen → Profiel → Taal`. De integratie detecteert automatisch en gebruikt je taalvoorkeur.

### **V: Welke talen worden ondersteund?**
A: Engels, Nederlands, Duits en Frans zijn volledig ondersteund voor zowel de config flow als Lovelace kaart.

### **V: Ik krijg authenticatiefouten**
A: Controleer je fresh-r.me inloggegevens en zorg ervoor dat je account actief is. De integratie vereist dezelfde inloggegevens als de fresh-r.me web dashboard.

### **V: Hoe los ik verbindingsproblemen op?**
A: Schakel debug logging in je `configuration.yaml`:
```yaml
logger:
  default: warning
  logs:
    custom_components.fresh_r: debug
```

### **V: Kan ik dit gebruiken met meerdere Fresh-r apparaten?**
A: Ja, de integratie ontdekt automatisch alle Fresh-r apparaten die aan je account gekoppeld zijn.

### **V: Wat is de rate limiting voor API calls?**
A: De integratie gebruikt veilige intervallen: maximaal 12 login requests per uur en 4 data requests per uur.

### **V: Hoe importeer ik de Grafana dashboard?**
A: In Grafana, ga naar `Dashboards → Import → Upload JSON file` en selecteer de `fresh_r_dashboard.json` uit het ZIP bestand.
