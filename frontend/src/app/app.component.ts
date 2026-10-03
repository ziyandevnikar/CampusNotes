import { Component, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';

const API_URL = 'http://127.0.0.1:5000';

@Component({
  selector: 'app-root',
  standalone: true,
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent implements OnInit {
  // 'checking' | 'connected' | 'unreachable'
  backendStatus = signal('checking');
  backendMessage = signal('');

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.http.get<{ message: string }>(`${API_URL}/ping`).subscribe({
      next: (res) => {
        this.backendStatus.set('connected');
        this.backendMessage.set(res.message);
      },
      error: () => this.backendStatus.set('unreachable'),
    });
  }
}
