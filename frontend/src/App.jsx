import { useState } from 'react';
import './App.css';

function App() {
  const [dni, setDni] = useState('');
  const [contribuyente, setContribuyente] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const buscarContribuyente = async () => {
    setLoading(true);
    setError(null);
    setContribuyente(null);
    try {
      const response = await fetch(`http://localhost:8000/contribuyentes/${dni}`);
      if (!response.ok) {
        throw new Error('Contribuyente no encontrado o error del servidor');
      }
      const data = await response.json();
      setContribuyente(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const iniciarPago = async () => {
    if (!contribuyente) return;

    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`http://localhost:8000/pagar?dni=${contribuyente.dni}&monto=${contribuyente.monto_mensual_impuesto}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      if (!response.ok) {
        throw new Error('Error al iniciar el pago');
      }
      const data = await response.json();
      if (data.payment_link) {
        window.location.href = data.payment_link; // Redirigir al usuario al enlace de pago
      } else {
        setError('No se recibió enlace de pago de MercadoPago.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="App">
      <h1>Portal de Pagos Municipales</h1>

      <div className="input-section">
        <input
          type="text"
          placeholder="Ingresa tu DNI"
          value={dni}
          onChange={(e) => setDni(e.target.value)}
        />
        <button onClick={buscarContribuyente} disabled={loading}>
          {loading ? 'Buscando...' : 'Buscar'}
        </button>
      </div>

      {error && <p className="error-message">{error}</p>}
      {loading && <p>Cargando información...</p>}

      {contribuyente && (
        <div className="contribuyente-info">
          <h2>Información del Contribuyente</h2>
          <p><strong>Nombre:</strong> {contribuyente.nombre}</p>
          <p><strong>DNI:</strong> {contribuyente.dni}</p>
          <p><strong>Monto Mensual:</strong> ${contribuyente.monto_mensual_impuesto}</p>
          <p><strong>Deuda Actual:</strong> ${contribuyente.deuda}</p>
          <p><strong>Estado Suscripción:</strong> {contribuyente.estado_suscripcion}</p>

          <button onClick={iniciarPago} disabled={loading} className="pay-button">
            {loading ? 'Redirigiendo a MercadoPago...' : 'Pagar con MercadoPago'}
          </button>
        </div>
      )}
    </div>
  );
}

export default App;