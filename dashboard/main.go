package main

import (
	"database/sql"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	_ "github.com/lib/pq"
)

// Config
const (
	pgConnStr = "postgres://admin:password123@localhost:5432/seopc_metadata?sslmode=disable"
)

type model struct {
	db              *sql.DB
	scenesProcessed int
	latestTelemetry string
	err             error
}

type tickMsg time.Time

func tick() tea.Cmd {
	return tea.Tick(500*time.Millisecond, func(t time.Time) tea.Msg {
		return tickMsg(t)
	})
}

func initialModel() model {
	conn, err := sql.Open("postgres", pgConnStr)
	if err != nil {
		log.Fatal(err)
	}
	return model{
		db:              conn,
		scenesProcessed: 0,
		latestTelemetry: "Waiting...",
	}
}

func (m model) Init() tea.Cmd {
	return tick()
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.KeyMsg:
		if msg.String() == "q" || msg.String() == "ctrl+c" {
			return m, tea.Quit
		}
	case tickMsg:
		// Fetch stats from DB
		var count int
		err := m.db.QueryRow("SELECT COUNT(*) FROM processing_logs").Scan(&count)
		if err != nil {
			m.err = err
		} else {
			m.scenesProcessed = count
		}

		var filename string
		err = m.db.QueryRow("SELECT filename FROM processing_logs ORDER BY processed_at DESC LIMIT 1").Scan(&filename)
		if err == nil {
			m.latestTelemetry = filename
		}

		return m, tick()
	}
	return m, nil
}

func (m model) View() string {

	infoStyle := lipgloss.NewStyle().Foreground(lipgloss.Color("86"))
	
    status := "ORBITAL LINK ACTIVE" // Static as per requirements, could be dynamic
    statusColor := lipgloss.Color("42") // Green
    statusText := lipgloss.NewStyle().Foreground(statusColor).Render(status)

	s := fmt.Sprintf("\n  SEOPC DASHBOARD\n\n")
	s += fmt.Sprintf("  STATUS: %s\n\n", statusText)
	s += fmt.Sprintf("  SCENES PROCESSED: %d\n", m.scenesProcessed)
	s += fmt.Sprintf("  LATEST TELEMETRY: %s\n\n", m.latestTelemetry)
    
    if m.err != nil {
        s += fmt.Sprintf("  Error: %v\n", m.err)
    }

	s += infoStyle.Render("  Press q to quit\n")
	return s
}

func main() {
	p := tea.NewProgram(initialModel())
	if _, err := p.Run(); err != nil {
		fmt.Printf("Alas, there's been an error: %v", err)
		os.Exit(1)
	}
}
