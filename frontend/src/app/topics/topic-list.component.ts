import { Component, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { Router } from "@angular/router";
import { ApiService, Topic } from "../services/api.service";
import { AuthService } from "../services/auth.service";

@Component({
  selector: "app-topic-list",
  standalone: true,
  imports: [CommonModule],
  styleUrls: ["./topic-list.component.scss"],
  templateUrl: "./topic-list.component.html",
})
export class TopicListComponent implements OnInit {
  topics: Topic[] = [];
  loading = true;

  constructor(
    private api: ApiService,
    private router: Router,
  ) {}

  ngOnInit(): void {
    this.api.getTopics().subscribe({
      next: (t) => {
        this.topics = t;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      },
    });
  }

  start(topic: Topic): void {
    this.router.navigate(["/conversation"], {
      queryParams: { topicId: topic.id, title: topic.title },
    });
  }
}
