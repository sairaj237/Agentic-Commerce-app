import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './App.css'

function App() {
  const [messages, setMessages] = useState([
    { role: 'agent', content: 'Hello! I am your AI Cafe Assistant. I can help you order coffee, pastries, and handle your checkout securely. What would you like today?' }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const [cart, setCart] = useState([]);
  const [sessionId] = useState(() => crypto.randomUUID());

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const triggerRazorpayCheckout = (checkoutData) => {
    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.onload = () => {
      const options = {
        key: checkoutData.key_id,
        amount: checkoutData.amount,
        currency: checkoutData.currency,
        name: 'Agentic Cafe',
        description: 'Test Transaction',
        order_id: checkoutData.order_id,
        handler: async function (response) {
          console.log("Payment Successful!", response);
          try {
            const verifyRes = await fetch('http://localhost:8000/verify_payment', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                razorpay_order_id: response.razorpay_order_id,
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_signature: response.razorpay_signature
              })
            });
            if (verifyRes.ok) {
              alert(`Payment Verified Successfully!\nPayment ID: ${response.razorpay_payment_id}`);
              setMessages(prev => [...prev, { role: 'user', content: 'Payment was successful and verified by the server!' }]);
            } else {
              alert('Payment verification failed on the server.');
            }
          } catch (e) {
            alert('Network error verifying payment.');
          }
        },
        prefill: {
          name: 'Agent User',
          email: 'agent@example.com',
          contact: '9999999999'
        },
        theme: {
          color: '#3399cc'
        }
      };
      const rzp1 = new window.Razorpay(options);
      rzp1.on('payment.failed', function (response){
        alert("Payment Failed: " + response.error.description);
      });
      rzp1.open();
    };
    document.body.appendChild(script);
  };

  const handleSend = async () => {
    if (!input.trim()) return;
    
    const userMsg = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setIsLoading(true);

    try {
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg, session_id: sessionId })
      });
      
      const data = await response.json();
      setMessages(prev => [...prev, { role: 'agent', content: data.reply }]);
      if (data.cart) {
        setCart(data.cart);
      }
      if (data.checkout) {
        triggerRazorpayCheckout(data.checkout);
      }
    } catch (error) {
      setMessages(prev => [...prev, { role: 'agent', content: 'Sorry, I am having trouble connecting to the server.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app-container">
      <div className="chat-section">
        <div className="chat-header">
          <h2>Agentic Commerce <span className="status-indicator"></span></h2>
        </div>
        
        <div className="chat-messages">
          {messages.map((msg, idx) => (
            <div key={idx} className={`message ${msg.role}`}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
            </div>
          ))}
          {isLoading && (
            <div className="message agent" style={{opacity: 0.7}}>
              Thinking...
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="chat-input-area">
          <input 
            type="text" 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="E.g., I'd like to buy a coffee..."
            disabled={isLoading}
          />
          <button onClick={handleSend} disabled={isLoading || !input.trim()}>
            Send
          </button>
        </div>
      </div>

      <div className="sidebar">
        <div className="panel">
          <h3>Your Cart</h3>
          {cart.length === 0 ? (
            <div className="cart-item">
              <span>Empty</span>
              <span>₹0.00</span>
            </div>
          ) : (
            cart.map((item, idx) => (
              <div key={idx} className="cart-item">
                <span>{item.quantity}x {item.name}</span>
                <span>₹{(item.price * item.quantity).toFixed(2)}</span>
              </div>
            ))
          )}
          <div className="cart-total">
            <span>Total</span>
            <span>₹{cart.reduce((acc, item) => acc + (item.price * item.quantity), 0).toFixed(2)}</span>
          </div>
        </div>
        
        <div className="panel">
          <h3>Security & Bounds</h3>
          <p style={{fontSize: '0.9rem', color: 'var(--text-muted)'}}>
            Pre-authorized limit: <strong>₹500.00</strong>
            <br/>
            Any transaction above this amount will be automatically blocked by the gatekeeper.
          </p>
        </div>
      </div>
    </div>
  )
}

export default App
